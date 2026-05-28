"""Bounded statistics primitive for executor latency digests.

Identical primitive as the queue layer's :class:`WaitDigest` — a
running mean + a deterministic reservoir for percentile approximation.
Replay-deterministic: identical event streams produce identical
percentile estimates.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from asyncviz.instrumentation.executor.metrics.executor_metrics_models import (
    ExecutorLatencySnapshot,
)


@dataclass(slots=True)
class LatencyDigest:
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

    def snapshot(self) -> ExecutorLatencySnapshot:
        if self.count == 0:
            return ExecutorLatencySnapshot()
        mean = self.sum_seconds / self.count
        if not self._samples:
            return ExecutorLatencySnapshot(count=self.count, mean_seconds=mean)
        ordered = sorted(self._samples)
        return ExecutorLatencySnapshot(
            count=self.count,
            mean_seconds=mean,
            p50_seconds=_percentile(ordered, 0.50),
            p95_seconds=_percentile(ordered, 0.95),
            p99_seconds=_percentile(ordered, 0.99),
            max_seconds=self.max_seconds,
        )


def _percentile(sorted_samples: list[float], q: float) -> float:
    if not sorted_samples:
        return 0.0
    if q <= 0.0:
        return sorted_samples[0]
    if q >= 1.0:
        return sorted_samples[-1]
    index = int(q * len(sorted_samples))
    if index >= len(sorted_samples):
        index = len(sorted_samples) - 1
    return sorted_samples[index]
