"""cProfile-backed CPU profiling helper.

Use this when a benchmark's p95 spikes unexpectedly + you need a
function-level breakdown. Returns the top-N entries by cumulative
time so the diagnostics layer can render them in a report.
"""

from __future__ import annotations

import cProfile
import io
import pstats
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CpuProfileEntry:
    function_name: str
    cumulative_seconds: float
    call_count: int


@dataclass(frozen=True, slots=True)
class CpuProfileReport:
    entries: tuple[CpuProfileEntry, ...]
    total_calls: int
    total_seconds: float
    raw_text: str


def profile_callable(
    fn: Callable[[], None],
    *,
    top_n: int = 20,
) -> CpuProfileReport:
    """Profile one invocation + return the top-N entries."""
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        fn()
    finally:
        profiler.disable()
    buf = io.StringIO()
    stats = pstats.Stats(profiler, stream=buf).sort_stats("cumulative")
    stats.print_stats(top_n)
    entries: list[CpuProfileEntry] = []
    total_calls = 0
    total_seconds = 0.0
    for func, info in stats.stats.items():  # type: ignore[attr-defined]
        # info = (cc, nc, tt, ct, callers)
        cc, nc, _tt, ct, _callers = info
        total_calls += nc
        total_seconds = max(total_seconds, ct)
        filename, lineno, function = func
        entries.append(
            CpuProfileEntry(
                function_name=f"{filename}:{lineno}({function})",
                cumulative_seconds=ct,
                call_count=cc,
            ),
        )
    entries.sort(key=lambda e: e.cumulative_seconds, reverse=True)
    return CpuProfileReport(
        entries=tuple(entries[:top_n]),
        total_calls=total_calls,
        total_seconds=total_seconds,
        raw_text=buf.getvalue(),
    )
