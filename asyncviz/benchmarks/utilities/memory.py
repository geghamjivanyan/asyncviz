"""tracemalloc-backed allocation measurement.

Used only when ``BenchmarkConfig.track_allocations=True`` — turning
it on slows the benchmark by ~10x because every allocation gets
tracked.
"""

from __future__ import annotations

import tracemalloc
from dataclasses import dataclass
from typing import Final

DEFAULT_TRACE_FRAMES: Final[int] = 1
"""Single-frame traces minimize tracemalloc overhead while still
giving the diagnostics layer a hook to do deeper analysis if it
takes its own snapshots."""


@dataclass(frozen=True, slots=True)
class AllocationSample:
    """One allocation observation."""

    delta_bytes: int
    peak_bytes: int


@dataclass(slots=True)
class AllocationBaseline:
    """Per-benchmark allocation snapshot baseline."""

    started_bytes: int
    peak_at_start: int


def capture_allocation_baseline() -> AllocationBaseline:
    """Reset peak + capture current."""
    if not tracemalloc.is_tracing():
        tracemalloc.start(DEFAULT_TRACE_FRAMES)
    tracemalloc.reset_peak()
    current, peak = tracemalloc.get_traced_memory()
    return AllocationBaseline(started_bytes=current, peak_at_start=peak)


def sample_allocation_delta(baseline: AllocationBaseline) -> AllocationSample:
    """Compute current allocation delta vs the baseline."""
    if not tracemalloc.is_tracing():
        return AllocationSample(delta_bytes=0, peak_bytes=0)
    current, peak = tracemalloc.get_traced_memory()
    return AllocationSample(
        delta_bytes=current - baseline.started_bytes,
        peak_bytes=peak,
    )


def stop_tracing_if_active() -> None:
    if tracemalloc.is_tracing():
        tracemalloc.stop()
