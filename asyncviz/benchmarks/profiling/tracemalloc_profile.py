"""tracemalloc-backed allocation profile.

Captures a snapshot before + after one invocation, returns the
top-N allocation-site deltas.
"""

from __future__ import annotations

import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AllocationProfileEntry:
    file: str
    line: int
    size_bytes: int
    count: int


@dataclass(frozen=True, slots=True)
class AllocationProfileReport:
    entries: tuple[AllocationProfileEntry, ...]
    total_delta_bytes: int
    peak_bytes: int


def profile_allocations(
    fn: Callable[[], None],
    *,
    top_n: int = 20,
    frames: int = 1,
) -> AllocationProfileReport:
    """Profile one invocation's allocations."""
    started_tracing_here = not tracemalloc.is_tracing()
    if started_tracing_here:
        tracemalloc.start(frames)
    tracemalloc.clear_traces()
    tracemalloc.reset_peak()
    before = tracemalloc.take_snapshot()
    fn()
    after = tracemalloc.take_snapshot()
    diff = after.compare_to(before, "lineno")
    total_delta = sum(stat.size_diff for stat in diff)
    _current, peak = tracemalloc.get_traced_memory()
    entries: list[AllocationProfileEntry] = []
    for stat in diff[:top_n]:
        frame = stat.traceback[0]
        entries.append(
            AllocationProfileEntry(
                file=frame.filename,
                line=frame.lineno,
                size_bytes=stat.size_diff,
                count=stat.count_diff,
            ),
        )
    if started_tracing_here:
        tracemalloc.stop()
    return AllocationProfileReport(
        entries=tuple(entries),
        total_delta_bytes=total_delta,
        peak_bytes=peak,
    )
