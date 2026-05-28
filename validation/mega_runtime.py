"""AsyncViz full-system integration validation runtime.

Runs scaled-down versions of every focused validation runtime in
parallel so the dashboard shows every panel populated simultaneously.
Intended as the final smoke validation before declaring the
instrumentation stack healthy end-to-end.

Subsystems exercised concurrently:

  * **Queues**        — saturating + bursty + starving profiles (from
    :mod:`queue_stress_runtime`, lower task counts).
  * **Semaphores**    — contention + starvation + churn (from
    :mod:`semaphore_runtime`, fewer workers).
  * **Gather trees**  — wide fanouts + nested trees + cascading
    cancels (from :mod:`gather_dependency_runtime`).
  * **Executors**     — thread pool baseline + saturator + mixed
    scheduling (process pool deliberately off to keep CPU pressure
    bounded on developer laptops).
  * **Blocking**      — one heavy offender + one burst offender so
    warning groups populate without dominating CPU.
  * **Cancellation churn** — periodically cancels a small fanout to
    keep the cancellation event channel warm.

Because every panel ticks, this is also the right runtime to use
when debugging a "is the dashboard rendering the panel I just
added?" question — open the dashboard, run mega_runtime, watch the
target surface fill in.

Run with::

    asyncviz run validation/mega_runtime.py --duration 180

Recommended duration: 120-300 s. Shorter and some lifecycle states
(warning recovery, executor saturation backoff) don't have time to
appear.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor

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

logger = logging.getLogger("validation.mega")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Full-system integration validation workload",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    add_common_args(parser)
    parser.add_argument(
        "--enable-blocking",
        action="store_true",
        default=True,
        help="enable blocking offenders (default on)",
    )
    parser.add_argument(
        "--disable-blocking",
        action="store_false",
        dest="enable_blocking",
        help="run without blocking offenders (no warnings will be emitted)",
    )
    return parser.parse_args(argv)


# ── Queue subsystem ──────────────────────────────────────────────────────


async def mini_queue_pipeline(stop: asyncio.Event, rng: random.Random) -> None:
    queue: asyncio.Queue[int] = asyncio.Queue(maxsize=6)
    counter = [0]

    async def producer() -> None:
        tick = 0
        while not stop.is_set():
            tick += 1
            if tick % 6 == 0:
                # Burst.
                for _ in range(10):
                    if stop.is_set():
                        return
                    counter[0] += 1
                    await queue.put(counter[0])
                await asyncio.sleep(0.05)
            else:
                counter[0] += 1
                await queue.put(counter[0])
                await asyncio.sleep(rng.uniform(0.04, 0.10))

    async def slow_consumer() -> None:
        while not stop.is_set():
            try:
                _ = await asyncio.wait_for(queue.get(), timeout=0.5)
            except TimeoutError:
                continue
            await asyncio.sleep(rng.uniform(0.15, 0.30))
            queue.task_done()

    async def fast_consumer() -> None:
        while not stop.is_set():
            try:
                _ = await asyncio.wait_for(queue.get(), timeout=0.5)
            except TimeoutError:
                continue
            await asyncio.sleep(rng.uniform(0.02, 0.05))
            queue.task_done()

    tasks = [
        asyncio.create_task(producer(), name="mega-queue-producer"),
        asyncio.create_task(slow_consumer(), name="mega-queue-slow"),
        asyncio.create_task(fast_consumer(), name="mega-queue-fast"),
    ]
    try:
        await stop.wait()
    finally:
        await cancel_all(tasks)
        while not queue.empty():
            with contextlib.suppress(asyncio.QueueEmpty):
                queue.get_nowait()
                queue.task_done()


# ── Semaphore subsystem ──────────────────────────────────────────────────


async def mini_semaphore_pipeline(stop: asyncio.Event, rng: random.Random) -> None:
    sem = asyncio.Semaphore(2)

    async def worker(name: str) -> None:
        while not stop.is_set():
            async with sem:
                await asyncio.sleep(rng.uniform(0.10, 0.25))
            await asyncio.sleep(rng.uniform(0.01, 0.05))

    tasks = [
        asyncio.create_task(worker(f"mega-sem-{i}"), name=f"mega-sem-{i}") for i in range(8)
    ]
    try:
        await stop.wait()
    finally:
        await cancel_all(tasks)


# ── Gather / dependency subsystem ────────────────────────────────────────


async def mini_gather_pipeline(stop: asyncio.Event, rng: random.Random) -> None:
    iteration = 0
    while not stop.is_set():
        iteration += 1

        async def leaf(idx: int) -> int:
            await asyncio.sleep(rng.uniform(0.05, 0.30))
            return idx

        async def branch(branch_idx: int) -> list[int]:
            return await asyncio.gather(
                *(
                    asyncio.create_task(leaf(branch_idx * 10 + j), name=f"mega-leaf-{iteration}-{branch_idx}-{j}")
                    for j in range(3)
                ),
            )

        # ``asyncio.gather`` returns a Future, not a coroutine — keep
        # the handle directly so we can cancel it mid-flight on the
        # exercise-cascading-cancel branch.
        tree = asyncio.gather(
            *(
                asyncio.create_task(branch(b), name=f"mega-branch-{iteration}-{b}")
                for b in range(3)
            ),
        )
        try:
            if iteration % 5 == 0:
                await asyncio.sleep(0.2)
                tree.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await tree
            else:
                await tree
        except Exception:
            logger.exception("mini-gather iteration failed")
        await asyncio.sleep(rng.uniform(0.5, 1.5))


# ── Executor subsystem ──────────────────────────────────────────────────


def _cpu_burn(iterations: int) -> int:
    acc = 0
    for i in range(iterations):
        acc = (acc + i * i) & 0xFFFF_FFFF
    return acc


def _io_block(duration: float) -> str:
    time.sleep(duration)
    return f"io-{duration}"


async def mini_executor_pipeline(pool: ThreadPoolExecutor, stop: asyncio.Event, rng: random.Random) -> None:
    loop = asyncio.get_running_loop()
    cycle = 0
    while not stop.is_set():
        cycle += 1
        # Steady load.
        await loop.run_in_executor(pool, _cpu_burn, 200)
        if cycle % 4 == 0:
            # Periodic burst that overruns the pool.
            futures = [
                loop.run_in_executor(pool, _io_block, rng.uniform(0.10, 0.20)) for _ in range(6)
            ]
            await asyncio.gather(*futures)
        await asyncio.sleep(rng.uniform(0.05, 0.15))


# ── Blocking subsystem ──────────────────────────────────────────────────


async def mini_blocking_offender(stop: asyncio.Event, rng: random.Random) -> None:
    # Warm-up before the first block so the lag baseline settles.
    try:
        await asyncio.wait_for(stop.wait(), timeout=4.0)
        return
    except TimeoutError:
        pass
    count = 0
    while not stop.is_set():
        count += 1
        dur = rng.uniform(0.30, 0.45)
        logger.info("mega-blocking #%s blocking %.0f ms", count, dur * 1000)
        time.sleep(dur)  # noqa: ASYNC251 — intentional
        await asyncio.sleep(rng.uniform(3.0, 5.0))


async def mini_burst_blocking(stop: asyncio.Event, rng: random.Random) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=6.0)
        return
    except TimeoutError:
        pass
    burst = 0
    while not stop.is_set():
        burst += 1
        for _ in range(4):
            time.sleep(rng.uniform(0.20, 0.25))  # noqa: ASYNC251 — intentional
            await asyncio.sleep(0.005)
            if stop.is_set():
                return
        logger.info("mega-burst-blocking #%s complete", burst)
        await asyncio.sleep(rng.uniform(8.0, 12.0))


# ── Cancellation churn ───────────────────────────────────────────────────


async def cancellation_churn(stop: asyncio.Event, rng: random.Random) -> None:
    iteration = 0
    while not stop.is_set():
        iteration += 1

        async def slow(i: int) -> None:
            await asyncio.sleep(rng.uniform(1.5, 2.5))

        children = [
            asyncio.create_task(slow(i), name=f"churn-{iteration}-{i}") for i in range(5)
        ]
        await asyncio.sleep(rng.uniform(0.2, 0.5))
        logger.info("cancellation-churn #%s cancelling 5 tasks", iteration)
        for c in children:
            c.cancel()
        await asyncio.gather(*children, return_exceptions=True)
        await asyncio.sleep(rng.uniform(6.0, 10.0))


# ── Orchestrator ─────────────────────────────────────────────────────────


async def run_workload(args: argparse.Namespace) -> None:
    config = common_from_namespace(args)
    rng = random.Random(config.seed)
    stop = asyncio.Event()
    install_signal_handlers(stop)
    logger.info("mega validation starting: duration=%.0fs", config.duration_seconds)

    pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="asyncviz-mega")

    tasks: list[asyncio.Task[object]] = [
        asyncio.create_task(
            mini_queue_pipeline(stop, random.Random(rng.random())),
            name="mega-queue",
        ),
        asyncio.create_task(
            mini_semaphore_pipeline(stop, random.Random(rng.random())),
            name="mega-semaphore",
        ),
        asyncio.create_task(
            mini_gather_pipeline(stop, random.Random(rng.random())),
            name="mega-gather",
        ),
        asyncio.create_task(
            mini_executor_pipeline(pool, stop, random.Random(rng.random())),
            name="mega-executor",
        ),
        asyncio.create_task(
            cancellation_churn(stop, random.Random(rng.random())),
            name="mega-cancellation",
        ),
    ]
    if args.enable_blocking:
        tasks.extend(
            (
                asyncio.create_task(
                    mini_blocking_offender(stop, random.Random(rng.random())),
                    name="mega-blocking",
                ),
                asyncio.create_task(
                    mini_burst_blocking(stop, random.Random(rng.random())),
                    name="mega-burst-blocking",
                ),
            ),
        )

    try:
        await wait_for_shutdown(stop, config.duration_seconds)
    finally:
        await cancel_all(tasks)
        pool.shutdown(wait=False, cancel_futures=True)
        logger.info("mega validation shutdown complete")


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
