"""Lightweight duration histogram with percentile lookup.

The aggregator needs p50 / p95 / p99 for duration analytics but we don't
want to pull in a full streaming-percentiles library (HDR, t-digest) yet.
This module ships a bounded-reservoir histogram:

* The first ``capacity`` samples are stored verbatim.
* Past that, new samples replace a uniformly-random older sample
  (Vitter's Algorithm R reservoir sampling) — preserves a representative
  sample of the lifetime distribution.

Percentile reads sort the current reservoir and index — O(N log N) per
read, which is fine at the snapshot cadence we care about (every few
seconds). The implementation is intentionally simple; swapping in t-digest
later only touches this file.
"""

from __future__ import annotations

import random
import threading
from dataclasses import dataclass

DEFAULT_RESERVOIR_CAPACITY: int = 2048


@dataclass(frozen=True, slots=True)
class HistogramSnapshot:
    """Sortable, JSON-safe view of an :class:`ApproxHistogram`."""

    count: int
    min_value: float
    max_value: float
    mean: float
    p50: float
    p95: float
    p99: float
    sum_value: float
    samples: int


class ApproxHistogram:
    """Reservoir-sampled histogram. Thread-safe."""

    __slots__ = (
        "_capacity",
        "_count",
        "_lock",
        "_max",
        "_min",
        "_reservoir",
        "_rng",
        "_sum",
    )

    def __init__(
        self, *, capacity: int = DEFAULT_RESERVOIR_CAPACITY, seed: int | None = None
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._lock = threading.Lock()
        self._reservoir: list[float] = []
        self._count = 0
        self._sum = 0.0
        self._min = float("inf")
        self._max = float("-inf")
        # ``random.Random`` per histogram so determinism is opt-in (tests
        # can pass a seed without disturbing the global ``random`` state).
        self._rng = random.Random(seed)

    def observe(self, value: float) -> None:
        if value < 0:
            return  # we only track non-negative durations
        with self._lock:
            self._count += 1
            self._sum += value
            if value < self._min:
                self._min = value
            if value > self._max:
                self._max = value
            if len(self._reservoir) < self._capacity:
                self._reservoir.append(value)
                return
            # Vitter Algorithm R: index ∈ [0, count); if < capacity, replace.
            j = self._rng.randrange(0, self._count)
            if j < self._capacity:
                self._reservoir[j] = value

    def reset(self) -> None:
        with self._lock:
            self._reservoir.clear()
            self._count = 0
            self._sum = 0.0
            self._min = float("inf")
            self._max = float("-inf")

    @property
    def count(self) -> int:
        with self._lock:
            return self._count

    def snapshot(self) -> HistogramSnapshot:
        with self._lock:
            if self._count == 0:
                return HistogramSnapshot(
                    count=0,
                    min_value=0.0,
                    max_value=0.0,
                    mean=0.0,
                    p50=0.0,
                    p95=0.0,
                    p99=0.0,
                    sum_value=0.0,
                    samples=0,
                )
            sorted_samples = sorted(self._reservoir)
            return HistogramSnapshot(
                count=self._count,
                min_value=self._min,
                max_value=self._max,
                mean=self._sum / self._count,
                p50=_percentile(sorted_samples, 0.50),
                p95=_percentile(sorted_samples, 0.95),
                p99=_percentile(sorted_samples, 0.99),
                sum_value=self._sum,
                samples=len(sorted_samples),
            )


def _percentile(sorted_samples: list[float], q: float) -> float:
    """Linear interpolation between bracketing samples."""
    if not sorted_samples:
        return 0.0
    n = len(sorted_samples)
    if n == 1:
        return sorted_samples[0]
    pos = q * (n - 1)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_samples[lo] * (1 - frac) + sorted_samples[hi] * frac
