"""AsyncViz runtime smoke / validation workload.

Run with::

    asyncviz run sample_runtime.py

The CLI attaches AsyncViz instrumentation before this script executes,
so the workload below intentionally has *no* imports from ``asyncviz``
— it is a plain asyncio program. Every event it emits flows through
the runtime that the ``asyncviz run`` launcher has already started.

What this workload exercises
----------------------------
The script is purposely asymmetric so the dashboard sees real
backpressure rather than a steady-state blur:

* **Task lifecycle**       — multiple long-lived workers + bursts of
  short-lived ``create_task``-ed coroutines that complete on their
  own. The Tasks page should show rows entering / exiting RUNNING /
  COMPLETED.
* **Queue instrumentation** — a single bounded :class:`asyncio.Queue`
  is shared by all producers + consumers. The Queues page should show
  occupancy oscillating, wait-time spikes during bursts, and a drain
  curve after each burst.
* **Queue pressure + saturation** — producers periodically enter a
  "burst" mode (10 fast puts) while one consumer is intentionally
  slow, so the queue fills past its capacity and producers stall on
  ``put()``. That stall is what surfaces as saturation in the
  pressure metrics.
* **Blocking detection**    — a dedicated ``offender`` task does
  ``time.sleep(0.4)`` periodically. With the default thresholds
  (warning=50 ms, critical=250 ms) this trips the critical bucket;
  three of those in a row open a blocking warning group on the
  Warnings page with a captured stack frame.
* **``asyncio.gather`` fanout** — a coordinator task periodically
  gathers N short coroutines so the gather instrumentation engine
  records a fanout group and per-child child id resolution.
* **Runtime metrics**       — task counts, queue stats, gather
  activity, and warning rates all derive automatically from the
  events above; the Metrics page should update once per heartbeat.
* **WebSocket streaming**   — the dashboard's bridge subscribes to
  the same event bus; opening ``/timeline`` while this is running
  shows the deltas land live.

Behavior knobs
--------------
* ``--duration N``     — how long to keep generating activity (default 60s).
* ``--workers N``      — consumer count (default 3).
* ``--producers N``    — producer count (default 2).
* ``--seed N``         — RNG seed so a re-run produces the same shape (default 1).
* ``--queue-size N``   — bounded queue capacity (default 8).
* ``--no-blocking``    — disable the blocking offender (useful when validating
  green-path runs without warnings).

A SIGINT (Ctrl-C) or ``--duration`` elapsing both trigger graceful
shutdown: every spawned task is cancelled, awaited, and its
``CancelledError`` is swallowed so the process exits cleanly with no
warnings.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import random
import signal
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass

logger = logging.getLogger("sample_runtime")


# ── Configuration ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class WorkloadConfig:
    duration_seconds: float
    producers: int
    consumers: int
    queue_size: int
    seed: int
    enable_blocking_offender: bool
    gather_fanout: int
    burst_size: int


def _parse_args(argv: list[str] | None = None) -> WorkloadConfig:
    parser = argparse.ArgumentParser(
        description="AsyncViz runtime validation workload",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--duration", type=float, default=60.0, help="seconds to run")
    parser.add_argument("--producers", type=int, default=2)
    parser.add_argument("--workers", type=int, default=3, dest="consumers")
    parser.add_argument("--queue-size", type=int, default=8)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--gather-fanout", type=int, default=6)
    parser.add_argument("--burst-size", type=int, default=10)
    parser.add_argument(
        "--no-blocking",
        action="store_false",
        dest="enable_blocking_offender",
        help="disable the time.sleep() offender (no blocking warnings will fire)",
    )
    args = parser.parse_args(argv)
    return WorkloadConfig(
        duration_seconds=max(1.0, args.duration),
        producers=max(1, args.producers),
        consumers=max(1, args.consumers),
        queue_size=max(1, args.queue_size),
        seed=args.seed,
        enable_blocking_offender=args.enable_blocking_offender,
        gather_fanout=max(2, args.gather_fanout),
        burst_size=max(2, args.burst_size),
    )


# ── Workload primitives ───────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class WorkItem:
    """A single unit of work pushed onto the shared queue.

    The payload is intentionally trivial — the dashboard cares about
    the *shape* of the queue activity, not the contents.
    """

    sequence: int
    producer_id: int
    payload_size: int


async def producer(
    name: str,
    producer_id: int,
    queue: asyncio.Queue[WorkItem],
    config: WorkloadConfig,
    stop: asyncio.Event,
    sequence: list[int],
    rng: random.Random,
) -> None:
    """Push work onto the shared queue at varying cadence.

    Most ticks are a single ``put`` with a short randomized sleep,
    which keeps the consumers busy without flooding them. Every few
    ticks, the producer enters a *burst* — ``burst_size`` quick puts
    in a row that intentionally overrun the consumer rate so the
    queue saturates and back-pressure shows up on the dashboard.
    """
    logger.info("[%s] producer started", name)
    burst_every_n_ticks = 8
    tick = 0
    try:
        while not stop.is_set():
            tick += 1
            if tick % burst_every_n_ticks == 0:
                # Burst path: many puts back-to-back. When the queue
                # is full, ``put()`` itself awaits, which is the
                # "producer stall" the pressure metrics observe.
                for _ in range(config.burst_size):
                    if stop.is_set():
                        break
                    sequence[0] += 1
                    item = WorkItem(
                        sequence=sequence[0],
                        producer_id=producer_id,
                        payload_size=rng.randint(1, 32),
                    )
                    await queue.put(item)
                # Cool down briefly after a burst.
                await asyncio.sleep(0.05)
            else:
                sequence[0] += 1
                await queue.put(
                    WorkItem(
                        sequence=sequence[0],
                        producer_id=producer_id,
                        payload_size=rng.randint(1, 32),
                    ),
                )
                # Randomized spacing so producer events don't align
                # into a misleadingly regular pattern on the timeline.
                await asyncio.sleep(rng.uniform(0.03, 0.12))
    except asyncio.CancelledError:
        logger.info("[%s] producer cancelled", name)
        raise
    finally:
        logger.info("[%s] producer exited", name)


async def consumer(
    name: str,
    queue: asyncio.Queue[WorkItem],
    stop: asyncio.Event,
    rng: random.Random,
    *,
    slow: bool,
) -> None:
    """Drain the shared queue.

    One of the consumers is "slow" — its per-item processing sleep
    is biased higher, which lets the queue back up under producer
    bursts. The other consumers are quick, so the system drains
    between bursts and the dashboard sees the full backlog/drain
    oscillation cycle.
    """
    logger.info("[%s] consumer started (slow=%s)", name, slow)
    processed = 0
    try:
        while not stop.is_set():
            try:
                # ``wait_for`` so cancellation propagates immediately
                # rather than blocking inside ``queue.get()``.
                item = await asyncio.wait_for(queue.get(), timeout=0.5)
            except TimeoutError:
                continue
            try:
                processing_seconds = rng.uniform(0.15, 0.35) if slow else rng.uniform(0.02, 0.10)
                await asyncio.sleep(processing_seconds)
                processed += 1
                if processed % 20 == 0:
                    logger.info(
                        "[%s] processed %s items (last seq=%s, payload=%s)",
                        name,
                        processed,
                        item.sequence,
                        item.payload_size,
                    )
            finally:
                queue.task_done()
    except asyncio.CancelledError:
        logger.info("[%s] consumer cancelled (processed=%s)", name, processed)
        raise
    finally:
        logger.info("[%s] consumer exited (processed=%s)", name, processed)


async def gather_coordinator(
    stop: asyncio.Event,
    config: WorkloadConfig,
    rng: random.Random,
) -> None:
    """Periodically fan a batch of child coroutines out via ``asyncio.gather``.

    The gather instrumentation engine records the fanout as a group
    with per-child task ids, which surfaces on the Tasks /
    diagnostics pages as a parent → children relationship.
    """
    logger.info("gather coordinator started (fanout=%s)", config.gather_fanout)
    iteration = 0
    try:
        while not stop.is_set():
            iteration += 1

            async def child(idx: int, parent_iteration: int) -> int:
                # Mixed durations so the gather group doesn't finish
                # in lockstep — surfaces straggler behavior on the
                # dashboard.
                await asyncio.sleep(rng.uniform(0.05, 0.25))
                return parent_iteration * 1000 + idx

            results = await asyncio.gather(
                *(child(idx, iteration) for idx in range(config.gather_fanout)),
            )
            logger.info(
                "gather iteration %s complete (n=%s, last=%s)",
                iteration,
                len(results),
                results[-1],
            )
            # Idle long enough between fanouts that producers/consumers
            # dominate the timeline most of the time.
            await asyncio.sleep(rng.uniform(0.8, 1.5))
    except asyncio.CancelledError:
        logger.info("gather coordinator cancelled (iterations=%s)", iteration)
        raise
    finally:
        logger.info("gather coordinator exited (iterations=%s)", iteration)


async def blocking_offender(stop: asyncio.Event, rng: random.Random) -> None:
    """Intentionally block the event loop with ``time.sleep``.

    This is the only synchronous sleep in the workload. With the
    default thresholds (warning=50 ms, critical=250 ms) a 400 ms
    block lands solidly in the critical bucket. Five consecutive
    criticals open a blocking warning group on the dashboard, and
    the stack-capture engine attaches a captured frame so the
    warning entry shows where the block originated.
    """
    logger.warning(
        "blocking offender active — this WILL trigger blocking warnings; "
        "use --no-blocking to disable",
    )
    try:
        # Quick warm-up so the lag baseline settles before the first block.
        await asyncio.sleep(2.0)
        offenses = 0
        while not stop.is_set():
            offenses += 1
            block_seconds = rng.uniform(0.30, 0.50)
            logger.warning(
                "offender #%s: blocking loop for %.0fms",
                offenses,
                block_seconds * 1000,
            )
            # The actual blocking call. ``time.sleep`` does NOT yield
            # to the loop — the lag monitor will measure this as a
            # critical violation.
            time.sleep(block_seconds)  # noqa: ASYNC251 — intentional
            await asyncio.sleep(rng.uniform(0.8, 1.5))
    except asyncio.CancelledError:
        logger.info("blocking offender cancelled")
        raise


async def queue_observer(queue: asyncio.Queue[WorkItem], stop: asyncio.Event) -> None:
    """Log queue depth at a low cadence.

    Pure observability — gives a human running the script some
    feedback in the terminal while the dashboard is the real
    visualization surface.
    """
    try:
        while not stop.is_set():
            await asyncio.sleep(2.0)
            logger.info(
                "queue depth=%s/%s",
                queue.qsize(),
                queue.maxsize if queue.maxsize > 0 else "∞",
            )
    except asyncio.CancelledError:
        raise


# ── Orchestration ─────────────────────────────────────────────────────────


def _install_signal_handlers(loop: asyncio.AbstractEventLoop, stop: asyncio.Event) -> None:
    def _handler() -> None:
        if not stop.is_set():
            logger.info("signal received — initiating graceful shutdown")
            stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, RuntimeError):
            # ``add_signal_handler`` is unsupported on Windows under
            # ProactorEventLoop; the bootstrap loop on Unix accepts it.
            loop.add_signal_handler(sig, _handler)


async def _cancel_all(tasks: Iterable[asyncio.Task[object]]) -> None:
    """Cancel + await a group of tasks, swallowing CancelledError."""
    for task in tasks:
        if not task.done():
            task.cancel()
    # ``return_exceptions=True`` keeps a single misbehaving task from
    # masking the others. CancelledError is the expected outcome here
    # so we don't surface it as a workload failure.
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
            logger.exception("task ended with exception", exc_info=result)


async def run_workload(config: WorkloadConfig) -> None:
    rng = random.Random(config.seed)
    queue: asyncio.Queue[WorkItem] = asyncio.Queue(maxsize=config.queue_size)
    stop = asyncio.Event()
    sequence_counter = [0]  # boxed so producers share the same counter

    loop = asyncio.get_running_loop()
    _install_signal_handlers(loop, stop)

    tasks: list[asyncio.Task[object]] = []
    tasks.extend(
        asyncio.create_task(
            producer(
                name=f"producer-{i}",
                producer_id=i,
                queue=queue,
                config=config,
                stop=stop,
                sequence=sequence_counter,
                rng=random.Random(rng.random()),
            ),
            name=f"producer-{i}",
        )
        for i in range(config.producers)
    )
    tasks.extend(
        asyncio.create_task(
            consumer(
                name=f"consumer-{i}",
                queue=queue,
                stop=stop,
                rng=random.Random(rng.random()),
                slow=(i == 0),  # first consumer is slow → backlog forms
            ),
            name=f"consumer-{i}",
        )
        for i in range(config.consumers)
    )
    tasks.append(
        asyncio.create_task(
            gather_coordinator(stop, config, random.Random(rng.random())),
            name="gather-coordinator",
        ),
    )
    tasks.append(
        asyncio.create_task(queue_observer(queue, stop), name="queue-observer"),
    )
    if config.enable_blocking_offender:
        tasks.append(
            asyncio.create_task(
                blocking_offender(stop, random.Random(rng.random())),
                name="blocking-offender",
            ),
        )

    logger.info(
        "workload started: producers=%s consumers=%s queue_size=%s duration=%.0fs",
        config.producers,
        config.consumers,
        config.queue_size,
        config.duration_seconds,
    )

    # Either the duration elapses or a signal sets ``stop`` early.
    try:
        await asyncio.wait_for(stop.wait(), timeout=config.duration_seconds)
    except TimeoutError:
        logger.info("duration elapsed — signaling shutdown")
        stop.set()
    finally:
        await _cancel_all(tasks)
        # Drain anything the producers managed to enqueue after we
        # cancelled — best-effort, bounded by the queue size.
        while not queue.empty():
            with contextlib.suppress(asyncio.QueueEmpty):
                queue.get_nowait()
                queue.task_done()
        logger.info("workload shutdown complete")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    config = _parse_args(argv)
    try:
        asyncio.run(run_workload(config))
    except KeyboardInterrupt:
        # SIGINT before the loop installed its handler — rare, but
        # treat it the same way the in-loop handler does.
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
