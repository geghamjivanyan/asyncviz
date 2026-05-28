"""High-precision timing helpers for benchmarks.

Uses :func:`time.perf_counter_ns` exclusively — the only stdlib
clock that's both monotonic + nanosecond-precise. No floating-point
math on hot paths: durations stay integer-ns until the statistics
layer needs them.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class HighPrecisionTimer:
    """Context-managed perf timer.

        with HighPrecisionTimer() as t:
            do_work()
        elapsed_ns = t.elapsed_ns
    """

    started_ns: int = 0
    ended_ns: int = 0

    def __enter__(self) -> HighPrecisionTimer:
        self.started_ns = time.perf_counter_ns()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self.ended_ns = time.perf_counter_ns()

    @property
    def elapsed_ns(self) -> int:
        return max(0, self.ended_ns - self.started_ns)


def measure_callable(fn: Callable[[], Any]) -> int:
    """Measure one sync callable invocation. Returns ns elapsed."""
    started = time.perf_counter_ns()
    fn()
    return time.perf_counter_ns() - started


async def measure_callable_async(
    fn: Callable[[], Awaitable[Any]],
) -> int:
    """Measure one async callable invocation under ``await``.

    Wraps the timing inside the coroutine so the event loop's
    scheduling overhead is included in the measurement (which is
    what callers care about when they're benchmarking real async
    workloads)."""
    started = time.perf_counter_ns()
    await fn()
    return time.perf_counter_ns() - started


def run_async_blocking(coro: Awaitable[Any]) -> Any:
    """Run a coroutine to completion using a fresh event loop. Each
    call creates a new loop so test-suite event loops never leak
    between benchmarks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
