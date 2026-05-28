"""Bounded statistics primitives for queue wait-time digests.

These are deliberately tiny: a running mean + a bounded reservoir for
percentile approximation. The runtime metrics layer ships richer
histograms, but those are heavier than we want per-queue per-event in
the queue hot path.

The reservoir is a deterministic ring (not random) so replay produces
identical percentile estimates from identical event streams. Random
sampling would still be correct in expectation but would defeat the
"deterministic replay" guarantee the engine promises.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from asyncviz.instrumentation.queue.metrics.queue_metrics_models import (
    QueueWaitSnapshot,
)


@dataclass(slots=True)
class WaitDigest:
    """Bounded running statistics for a stream of wait-time samples."""

    capacity: int
    count: int = 0
    sum_seconds: float = 0.0
    max_seconds: float = 0.0
    _ring_index: int = 0
    _samples: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.capacity < 1:
            raise ValueError(f"capacity must be >= 1 (got {self.capacity})")

    def observe(self, seconds: float) -> None:
        if seconds < 0.0:
            seconds = 0.0
        self.count += 1
        self.sum_seconds += seconds
        if seconds > self.max_seconds:
            self.max_seconds = seconds
        if len(self._samples) < self.capacity:
            self._samples.append(seconds)
        else:
            self._samples[self._ring_index] = seconds
            self._ring_index = (self._ring_index + 1) % self.capacity

    def extend(self, samples: Iterable[float]) -> None:
        for s in samples:
            self.observe(s)

    def reset(self) -> None:
        self.count = 0
        self.sum_seconds = 0.0
        self.max_seconds = 0.0
        self._ring_index = 0
        self._samples.clear()

    def snapshot(self) -> QueueWaitSnapshot:
        if self.count == 0:
            return QueueWaitSnapshot()
        mean = self.sum_seconds / self.count
        if not self._samples:
            return QueueWaitSnapshot(count=self.count, mean_seconds=mean)
        # Sort a copy — _samples stays in arrival order so the ring still
        # works on the next observation.
        ordered = sorted(self._samples)
        return QueueWaitSnapshot(
            count=self.count,
            mean_seconds=mean,
            p50_seconds=_percentile(ordered, 0.50),
            p95_seconds=_percentile(ordered, 0.95),
            p99_seconds=_percentile(ordered, 0.99),
            max_seconds=self.max_seconds,
        )


def _percentile(sorted_samples: list[float], q: float) -> float:
    """Nearest-rank percentile on a pre-sorted list. ``q`` in ``[0, 1]``."""
    if not sorted_samples:
        return 0.0
    if q <= 0.0:
        return sorted_samples[0]
    if q >= 1.0:
        return sorted_samples[-1]
    # Standard NIST nearest-rank — index = ceil(q * N) - 1, clamped.
    index = int(q * len(sorted_samples))
    if index >= len(sorted_samples):
        index = len(sorted_samples) - 1
    return sorted_samples[index]
