"""AsyncViz queue-instrumentation validation runtime.

Drives :class:`QueueInstrumentationEngine` + :class:`QueueMetricsEngine`
through every observable state so each dashboard surface tied to
queue activity gets exercised:

  * **Occupancy oscillation** — a primary bounded queue with mixed
    producer/consumer rates that cycle between empty and full so the
    occupancy gauge has continuous motion.
  * **Saturation + backpressure** — producers periodically burst
    past the queue's capacity. The bounded ``put()`` stalls (the
    instrumentor records an ``asyncio.queue.full_wait``); after the
    consumers drain, throughput recovers.
  * **Empty-wait starvation** — a second queue is intentionally
    starved (producer rate << consumer rate) so consumers emit
    ``asyncio.queue.empty_wait`` events for the consumer-side
    starvation panel.
  * **Cross-queue contention** — a third queue shared by a slow
    consumer plus a fast one to trip the ``contention.detected``
    aggregation event.
  * **Bursty producer** — a fourth queue gets short, high-rate
    bursts every few seconds so the metrics histogram has visible
    spikes rather than a flat curve.

Run with::

    asyncviz run validation/queue_stress_runtime.py

Open ``/queues`` to see per-queue depth + pressure + contention; the
Metrics page should show the aggregated counters tick up.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import random
from dataclasses import dataclass

# ``asyncviz run`` executes the target via ``runpy.run_path`` — inject
# the script's directory so the sibling ``_common`` module imports.
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    add_common_args,
    cancel_all,
    common_from_namespace,
    install_signal_handlers,
    setup_logging,
    wait_for_shutdown,
)

logger = logging.getLogger("validation.queue")


@dataclass(frozen=True, slots=True)
class QueueProfile:
    name: str
    maxsize: int
    producers: int
    consumers: int
    burst_every: int
    burst_size: int
    slow_consumer: bool


# Each profile targets one named instrumentation behavior; the
# orchestrator runs all of them in parallel.
PROFILES: tuple[QueueProfile, ...] = (
    QueueProfile("oscillating", maxsize=8, producers=2, consumers=2, burst_every=10, burst_size=6, slow_consumer=True),
    QueueProfile("saturating", maxsize=4, producers=3, consumers=1, burst_every=4, burst_size=12, slow_consumer=False),
    QueueProfile("starving", maxsize=16, producers=1, consumers=4, burst_every=999, burst_size=0, slow_consumer=False),
    QueueProfile("contended", maxsize=6, producers=2, consumers=3, burst_every=8, burst_size=8, slow_consumer=True),
    QueueProfile("bursty", maxsize=10, producers=1, consumers=2, burst_every=3, burst_size=20, slow_consumer=False),
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Queue instrumentation validation workload",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    add_common_args(parser)
    return parser.parse_args(argv)


async def producer(
    name: str,
    queue: asyncio.Queue[int],
    profile: QueueProfile,
    stop: asyncio.Event,
    rng: random.Random,
    counter: list[int],
) -> None:
    logger.info("[%s] producer started", name)
    tick = 0
    try:
        while not stop.is_set():
            tick += 1
            if profile.burst_size > 0 and tick % profile.burst_every == 0:
                # Burst — overrun the consumers so the queue saturates
                # and producers block inside ``put()``.
                for _ in range(profile.burst_size):
                    if stop.is_set():
                        break
                    counter[0] += 1
                    await queue.put(counter[0])
                await asyncio.sleep(0.05)
            else:
                counter[0] += 1
                await queue.put(counter[0])
                # For the "starving" profile the producer deliberately
                # sleeps longer than the consumers so the queue stays
                # empty most of the time.
                lo, hi = (0.30, 0.60) if profile.name == "starving" else (0.03, 0.12)
                await asyncio.sleep(rng.uniform(lo, hi))
    except asyncio.CancelledError:
        raise
    finally:
        logger.info("[%s] producer exited (last sequence=%s)", name, counter[0])


async def consumer(
    name: str,
    queue: asyncio.Queue[int],
    profile: QueueProfile,
    stop: asyncio.Event,
    rng: random.Random,
    *,
    slow: bool,
) -> None:
    logger.info("[%s] consumer started (slow=%s)", name, slow)
    processed = 0
    try:
        while not stop.is_set():
            try:
                _item = await asyncio.wait_for(queue.get(), timeout=0.5)
            except TimeoutError:
                continue
            try:
                # Slow consumer sleeps long enough to let the queue back
                # up; fast consumer drains immediately.
                if slow:
                    await asyncio.sleep(rng.uniform(0.20, 0.40))
                else:
                    await asyncio.sleep(rng.uniform(0.01, 0.05))
                processed += 1
                if processed % 50 == 0:
                    logger.info(
                        "[%s] processed %s items (queue=%s/%s)",
                        name,
                        processed,
                        queue.qsize(),
                        profile.maxsize,
                    )
            finally:
                queue.task_done()
    except asyncio.CancelledError:
        raise
    finally:
        logger.info("[%s] consumer exited (processed=%s)", name, processed)


async def queue_observer(profile: QueueProfile, queue: asyncio.Queue[int], stop: asyncio.Event) -> None:
    """Periodic depth log per queue — terminal-side visibility."""
    try:
        while not stop.is_set():
            await asyncio.sleep(3.0)
            logger.info("[%s] depth=%s/%s", profile.name, queue.qsize(), profile.maxsize)
    except asyncio.CancelledError:
        raise


async def drive_profile(profile: QueueProfile, rng: random.Random, stop: asyncio.Event) -> None:
    queue: asyncio.Queue[int] = asyncio.Queue(maxsize=profile.maxsize)
    counter = [0]
    tasks: list[asyncio.Task[object]] = []
    for i in range(profile.producers):
        tasks.append(
            asyncio.create_task(
                producer(
                    f"{profile.name}-producer-{i}",
                    queue,
                    profile,
                    stop,
                    random.Random(rng.random()),
                    counter,
                ),
                name=f"{profile.name}-producer-{i}",
            ),
        )
    for i in range(profile.consumers):
        slow = profile.slow_consumer and i == 0
        tasks.append(
            asyncio.create_task(
                consumer(
                    f"{profile.name}-consumer-{i}",
                    queue,
                    profile,
                    stop,
                    random.Random(rng.random()),
                    slow=slow,
                ),
                name=f"{profile.name}-consumer-{i}",
            ),
        )
    tasks.append(
        asyncio.create_task(
            queue_observer(profile, queue, stop),
            name=f"{profile.name}-observer",
        ),
    )
    try:
        await stop.wait()
    finally:
        await cancel_all(tasks)
        # Best-effort drain so cancellation doesn't leave items hanging.
        while not queue.empty():
            with contextlib.suppress(asyncio.QueueEmpty):
                queue.get_nowait()
                queue.task_done()


async def run_workload(args: argparse.Namespace) -> None:
    config = common_from_namespace(args)
    rng = random.Random(config.seed)
    stop = asyncio.Event()
    install_signal_handlers(stop)
    logger.info(
        "queue stress validation starting: duration=%.0fs profiles=%s",
        config.duration_seconds,
        ",".join(p.name for p in PROFILES),
    )
    drivers = [
        asyncio.create_task(
            drive_profile(p, random.Random(rng.random()), stop),
            name=f"driver-{p.name}",
        )
        for p in PROFILES
    ]
    try:
        await wait_for_shutdown(stop, config.duration_seconds)
    finally:
        await cancel_all(drivers)
        logger.info("queue stress validation shutdown complete")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging(common_from_namespace(args))
    try:
        asyncio.run(run_workload(args))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
