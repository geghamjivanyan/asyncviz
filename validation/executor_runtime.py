"""AsyncViz executor-instrumentation validation runtime.

Exercises :class:`ExecutorInstrumentationEngine` and
:class:`ExecutorMetricsEngine` by submitting realistic workloads
through ``loop.run_in_executor`` against both
:class:`ThreadPoolExecutor` (CPU-light + IO-bound) and
:class:`ProcessPoolExecutor` (true CPU parallelism).

The script intentionally over-submits so the executor's worker pool
saturates and the saturation / contention / latency-spike aggregation
events fire:

  * **Thread pool — CPU-light**  — short-running calls (compute a
    small Fibonacci, sleep ~5 ms) submitted at ~40 Hz across 4
    workers. Stays inside the pool's capacity so the saturation
    counters stay low — useful for confirming the "normal load"
    baseline before stressing.
  * **Thread pool — IO-bound**   — ``time.sleep(0.2)`` calls
    submitted in bursts. Each worker holds the slot during the
    sleep so the queue depth oscillates; submitted faster than the
    pool can drain, so the queue-depth metric ticks up.
  * **Thread pool — saturation** — heavy long-running CPU tasks
    submitted faster than the pool can chew through them. Verifies
    the ``saturation.detected`` event lifecycle.
  * **Process pool**             — same heavy CPU tasks delegated
    to a :class:`ProcessPoolExecutor`. Asserts that the engine
    records executor-kind metadata correctly (thread vs. process)
    and that the slow inter-process pickling shows up as elevated
    submit→start latency.
  * **Mixed scheduling**         — a long-running async task that
    interleaves executor submissions with regular ``await``s,
    exercising the cross-cutting "task spent time in an executor
    call" attribution.

Run with::

    asyncviz run validation/executor_runtime.py

Open ``/executors`` for executor metrics + worker activity. The
``/diagnostics`` panel surfaces the saturation lifecycle.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

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

logger = logging.getLogger("validation.executor")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executor instrumentation validation workload",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    add_common_args(parser)
    parser.add_argument("--thread-workers", type=int, default=4)
    parser.add_argument("--process-workers", type=int, default=2)
    parser.add_argument(
        "--enable-process-pool",
        action="store_true",
        default=True,
        help="exercise ProcessPoolExecutor as well (default: on)",
    )
    parser.add_argument(
        "--disable-process-pool",
        action="store_false",
        dest="enable_process_pool",
        help="disable the ProcessPoolExecutor section (useful on restricted CI)",
    )
    return parser.parse_args(argv)


# ── Pure sync workers ────────────────────────────────────────────────────
# These functions run inside the executor; they must be top-level so the
# ProcessPoolExecutor can pickle them.


def _fib(n: int) -> int:
    """Tiny CPU work — bounded recursion. ~microseconds per call."""
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def io_bound_sleep(duration: float, tag: str) -> str:
    """Stand-in for blocking IO: blocks the worker for ``duration`` seconds."""
    time.sleep(duration)
    return f"io:{tag}"


def cpu_burn(iterations: int, tag: str) -> int:
    """CPU-bound burn used to saturate workers."""
    acc = 0
    for i in range(iterations):
        acc = (acc + _fib(20)) & 0xFFFF_FFFF
    return acc ^ hash(tag) & 0xFFFF_FFFF


# ── Async drivers ────────────────────────────────────────────────────────


async def thread_pool_baseline(pool: ThreadPoolExecutor, stop: asyncio.Event) -> None:
    """Steady-state, in-capacity load on the thread pool."""
    loop = asyncio.get_running_loop()
    tick = 0
    while not stop.is_set():
        tick += 1
        await loop.run_in_executor(pool, _fib, 25)
        await asyncio.sleep(0.025)
        if tick % 100 == 0:
            logger.info("thread-pool-baseline ticked %s", tick)


async def thread_pool_io_burst(pool: ThreadPoolExecutor, stop: asyncio.Event, rng: random.Random) -> None:
    """Bursts of blocking-IO calls submitted faster than the pool drains."""
    loop = asyncio.get_running_loop()
    burst = 0
    while not stop.is_set():
        burst += 1
        logger.info("io-burst #%s submitting 12 calls (pool workers limited)", burst)
        futures = [
            loop.run_in_executor(pool, io_bound_sleep, rng.uniform(0.15, 0.30), f"b{burst}.{i}")
            for i in range(12)
        ]
        await asyncio.gather(*futures)
        logger.info("io-burst #%s complete", burst)
        await asyncio.sleep(rng.uniform(3.0, 5.0))


async def thread_pool_saturator(pool: ThreadPoolExecutor, stop: asyncio.Event) -> None:
    """Sustained heavy submissions — trips the saturation detector."""
    loop = asyncio.get_running_loop()
    cycle = 0
    while not stop.is_set():
        cycle += 1
        logger.info("thread-saturator #%s submitting 8 heavy CPU jobs", cycle)
        futures = [
            loop.run_in_executor(pool, cpu_burn, 800, f"sat{cycle}.{i}") for i in range(8)
        ]
        await asyncio.gather(*futures)
        # Brief breather so saturation can recover before next round.
        await asyncio.sleep(2.0)


async def process_pool_demo(pool: ProcessPoolExecutor | None, stop: asyncio.Event) -> None:
    if pool is None:
        logger.info("process-pool disabled — skipping")
        return
    loop = asyncio.get_running_loop()
    cycle = 0
    while not stop.is_set():
        cycle += 1
        logger.info("process-pool #%s submitting 4 heavy CPU jobs", cycle)
        futures = [loop.run_in_executor(pool, cpu_burn, 600, f"pp{cycle}.{i}") for i in range(4)]
        await asyncio.gather(*futures)
        logger.info("process-pool #%s complete", cycle)
        await asyncio.sleep(4.0)


async def mixed_scheduling(pool: ThreadPoolExecutor, stop: asyncio.Event, rng: random.Random) -> None:
    """One long async task that interleaves executor calls with awaits.

    Validates that the per-task executor-time attribution surfaces:
    the dashboard should show this task spending most of its lifetime
    inside an executor rather than in the regular asyncio scheduler.
    """
    loop = asyncio.get_running_loop()
    iteration = 0
    while not stop.is_set():
        iteration += 1
        await loop.run_in_executor(pool, cpu_burn, 200, f"mixed{iteration}")
        await asyncio.sleep(rng.uniform(0.05, 0.15))
        await loop.run_in_executor(pool, io_bound_sleep, rng.uniform(0.05, 0.10), f"mixed{iteration}")
        await asyncio.sleep(rng.uniform(0.05, 0.15))


async def run_workload(args: argparse.Namespace) -> None:
    config = common_from_namespace(args)
    rng = random.Random(config.seed)
    stop = asyncio.Event()
    install_signal_handlers(stop)
    logger.info(
        "executor validation starting: duration=%.0fs threads=%s processes=%s",
        config.duration_seconds,
        args.thread_workers,
        args.process_workers if args.enable_process_pool else 0,
    )

    thread_pool = ThreadPoolExecutor(
        max_workers=args.thread_workers,
        thread_name_prefix="asyncviz-validation",
    )
    process_pool: ProcessPoolExecutor | None = None
    if args.enable_process_pool:
        try:
            process_pool = ProcessPoolExecutor(max_workers=args.process_workers)
        except Exception as exc:  # pragma: no cover — platform-dependent
            logger.warning("process pool unavailable (%s); continuing thread-only", exc)
            process_pool = None

    tasks = [
        asyncio.create_task(thread_pool_baseline(thread_pool, stop), name="thread-baseline"),
        asyncio.create_task(
            thread_pool_io_burst(thread_pool, stop, random.Random(rng.random())),
            name="thread-io-burst",
        ),
        asyncio.create_task(thread_pool_saturator(thread_pool, stop), name="thread-saturator"),
        asyncio.create_task(process_pool_demo(process_pool, stop), name="process-pool"),
        asyncio.create_task(
            mixed_scheduling(thread_pool, stop, random.Random(rng.random())),
            name="mixed-scheduling",
        ),
    ]

    try:
        await wait_for_shutdown(stop, config.duration_seconds)
    finally:
        await cancel_all(tasks)
        thread_pool.shutdown(wait=False, cancel_futures=True)
        if process_pool is not None:
            process_pool.shutdown(wait=False, cancel_futures=True)
        logger.info("executor validation shutdown complete")


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
