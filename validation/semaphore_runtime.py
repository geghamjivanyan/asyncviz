"""AsyncViz semaphore-instrumentation validation runtime.

Exercises :class:`SemaphoreInstrumentationEngine` by running multiple
contention scenarios in parallel against semaphores of different
sizes. Each scenario targets a specific event the engine emits
(``acquire.started``, ``acquired``, ``released``,
``contention.detected``, ``wait.cancelled``).

Scenarios:

  * **Heavy contention**   — :class:`asyncio.Semaphore` (value=2)
    with 12 tasks racing for it, each holding for 100-300 ms.
    Most tasks spend most of their time in ``acquire.started`` →
    ``acquired`` wait gaps; the contention aggregation event
    fires repeatedly.
  * **Starvation**         — value=1 semaphore where one task
    holds the permit for ~3 s while 8 short-hold tasks queue.
    Surfaces extreme wait-time outliers; useful for the
    starvation panel.
  * **Fairness churn**     — value=4 with 20 tasks acquiring +
    releasing in a tight loop (50 ms hold, 10 ms gap).
    High-frequency acquire/release pairs, low contention. Should
    NOT trigger the contention detector — useful negative test.
  * **Cancellation races** — every ~6 s, 4 tasks that are waiting
    on a saturated semaphore get cancelled mid-wait. Verifies
    ``wait.cancelled`` events and that the queue depth metric
    updates correctly when a waiter goes away without acquiring.

Run with::

    asyncviz run validation/semaphore_runtime.py

Open ``/semaphores`` to see per-semaphore wait/hold metrics; the
Diagnostics page surfaces the contention lifecycle.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random

# ``asyncviz run`` executes the target via ``runpy.run_path`` — inject
# the script's directory so the sibling ``_common`` module imports.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (
    add_common_args,
    cancel_all,
    common_from_namespace,
    install_signal_handlers,
    setup_logging,
    wait_for_shutdown,
)

logger = logging.getLogger("validation.semaphore")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Semaphore instrumentation validation workload",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    add_common_args(parser)
    return parser.parse_args(argv)


async def contended_worker(
    name: str,
    sem: asyncio.Semaphore,
    rng: random.Random,
    stop: asyncio.Event,
) -> None:
    holds = 0
    try:
        while not stop.is_set():
            async with sem:
                holds += 1
                await asyncio.sleep(rng.uniform(0.10, 0.30))
            # Tiny gap so the next acquire is a genuine new contention event.
            await asyncio.sleep(rng.uniform(0.005, 0.030))
    except asyncio.CancelledError:
        raise
    finally:
        logger.info("[%s] held %s times", name, holds)


async def starvation_holder(sem: asyncio.Semaphore, stop: asyncio.Event) -> None:
    """One task that holds the only permit for ~3 s at a time.

    The starving waiters in :func:`starvation_waiter` will queue
    behind this — exactly what the starvation diagnostic surfaces.
    """
    cycle = 0
    try:
        while not stop.is_set():
            cycle += 1
            async with sem:
                logger.info("starvation-holder #%s holding permit for 3.0s", cycle)
                await asyncio.sleep(3.0)
            await asyncio.sleep(0.2)
    except asyncio.CancelledError:
        raise


async def starvation_waiter(
    name: str,
    sem: asyncio.Semaphore,
    stop: asyncio.Event,
    rng: random.Random,
) -> None:
    acquired = 0
    try:
        while not stop.is_set():
            async with sem:
                acquired += 1
                await asyncio.sleep(rng.uniform(0.05, 0.10))
            await asyncio.sleep(rng.uniform(0.05, 0.15))
    except asyncio.CancelledError:
        raise
    finally:
        logger.info("[%s] eventually acquired %s times", name, acquired)


async def fairness_worker(
    name: str,
    sem: asyncio.Semaphore,
    rng: random.Random,
    stop: asyncio.Event,
) -> None:
    """Light hold + short gap — low-contention churn."""
    holds = 0
    try:
        while not stop.is_set():
            async with sem:
                holds += 1
                await asyncio.sleep(rng.uniform(0.04, 0.06))
            await asyncio.sleep(rng.uniform(0.008, 0.015))
    except asyncio.CancelledError:
        raise
    finally:
        logger.info("[%s] fairness churn: %s holds", name, holds)


async def cancellation_demo(
    sem: asyncio.Semaphore,
    stop: asyncio.Event,
    rng: random.Random,
) -> None:
    """Periodically saturate the semaphore + cancel queued waiters.

    The demo holds the semaphore in a single task, spawns 4 waiters
    that block on ``acquire``, then cancels them mid-wait. The
    instrumentation should record 4 ``wait.cancelled`` events and
    the queue depth metric should drop to 0 without any new
    acquisitions.
    """
    iteration = 0
    while not stop.is_set():
        iteration += 1
        # Hold every permit so any new acquire blocks.
        holder = asyncio.create_task(
            _block_forever_holder(sem, stop),
            name=f"cancel-demo-holder-{iteration}",
        )
        await asyncio.sleep(0.05)
        waiters = [
            asyncio.create_task(
                _blocked_waiter(sem, f"cancel-demo-{iteration}-w{i}"),
                name=f"cancel-demo-{iteration}-w{i}",
            )
            for i in range(4)
        ]
        # Let them queue up.
        await asyncio.sleep(rng.uniform(0.2, 0.4))
        logger.info("cancellation-demo #%s cancelling 4 waiters", iteration)
        for w in waiters:
            w.cancel()
        await asyncio.gather(*waiters, return_exceptions=True)
        holder.cancel()
        await asyncio.gather(holder, return_exceptions=True)
        # Drain any permits the holder grabbed; reset to "all available"
        # so the next iteration starts clean.
        await asyncio.sleep(rng.uniform(5.0, 7.0))


async def _block_forever_holder(sem: asyncio.Semaphore, stop: asyncio.Event) -> None:
    async with sem:
        await stop.wait()


async def _blocked_waiter(sem: asyncio.Semaphore, name: str) -> None:
    try:
        async with sem:
            # Should never reach here in the cancellation demo.
            await asyncio.sleep(0.0)
    except asyncio.CancelledError:
        logger.info("[%s] cancelled while waiting", name)
        raise


async def run_workload(args: argparse.Namespace) -> None:
    config = common_from_namespace(args)
    rng = random.Random(config.seed)
    stop = asyncio.Event()
    install_signal_handlers(stop)
    logger.info("semaphore validation starting: duration=%.0fs", config.duration_seconds)

    contended_sem = asyncio.Semaphore(2)
    starvation_sem = asyncio.Semaphore(1)
    fairness_sem = asyncio.Semaphore(4)
    cancel_sem = asyncio.Semaphore(1)

    tasks: list[asyncio.Task[object]] = []

    for i in range(12):
        tasks.append(
            asyncio.create_task(
                contended_worker(
                    f"contended-{i}",
                    contended_sem,
                    random.Random(rng.random()),
                    stop,
                ),
                name=f"contended-{i}",
            ),
        )
    tasks.append(
        asyncio.create_task(
            starvation_holder(starvation_sem, stop),
            name="starvation-holder",
        ),
    )
    for i in range(8):
        tasks.append(
            asyncio.create_task(
                starvation_waiter(
                    f"starve-w{i}",
                    starvation_sem,
                    stop,
                    random.Random(rng.random()),
                ),
                name=f"starve-w{i}",
            ),
        )
    for i in range(20):
        tasks.append(
            asyncio.create_task(
                fairness_worker(f"fair-{i}", fairness_sem, random.Random(rng.random()), stop),
                name=f"fair-{i}",
            ),
        )
    tasks.append(
        asyncio.create_task(
            cancellation_demo(cancel_sem, stop, random.Random(rng.random())),
            name="cancellation-demo",
        ),
    )

    try:
        await wait_for_shutdown(stop, config.duration_seconds)
    finally:
        await cancel_all(tasks)
        logger.info("semaphore validation shutdown complete")


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
