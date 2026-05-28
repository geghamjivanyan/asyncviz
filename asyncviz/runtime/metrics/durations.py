"""Duration aggregator — running stats + histogram per terminal bucket."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from asyncviz.runtime.metrics.histograms import (
    DEFAULT_RESERVOIR_CAPACITY,
    ApproxHistogram,
    HistogramSnapshot,
)


@dataclass(frozen=True, slots=True)
class DurationStatsSnapshot:
    """Immutable view of running duration aggregates."""

    count: int
    total_seconds: float
    min_seconds: float
    max_seconds: float
    mean_seconds: float
    histogram: HistogramSnapshot


class DurationAggregator:
    """Running-stats aggregator over per-task durations.

    Tracks count, sum, min, max, and feeds a bounded-reservoir histogram
    for percentiles. Bucketed by terminal state externally — e.g. the
    aggregator constructs three of these for COMPLETED / CANCELLED / FAILED.
    """

    __slots__ = ("_count", "_histogram", "_lock", "_max", "_min", "_sum")

    def __init__(
        self, *, capacity: int = DEFAULT_RESERVOIR_CAPACITY, seed: int | None = None
    ) -> None:
        self._lock = threading.Lock()
        self._count = 0
        self._sum = 0.0
        self._min = float("inf")
        self._max = float("-inf")
        self._histogram = ApproxHistogram(capacity=capacity, seed=seed)

    def observe(self, seconds: float | None) -> None:
        if seconds is None or seconds < 0:
            return
        with self._lock:
            self._count += 1
            self._sum += seconds
            if seconds < self._min:
                self._min = seconds
            if seconds > self._max:
                self._max = seconds
        self._histogram.observe(seconds)

    def reset(self) -> None:
        with self._lock:
            self._count = 0
            self._sum = 0.0
            self._min = float("inf")
            self._max = float("-inf")
        self._histogram.reset()

    def snapshot(self) -> DurationStatsSnapshot:
        with self._lock:
            count = self._count
            if count == 0:
                return DurationStatsSnapshot(
                    count=0,
                    total_seconds=0.0,
                    min_seconds=0.0,
                    max_seconds=0.0,
                    mean_seconds=0.0,
                    histogram=self._histogram.snapshot(),
                )
            return DurationStatsSnapshot(
                count=count,
                total_seconds=self._sum,
                min_seconds=self._min,
                max_seconds=self._max,
                mean_seconds=self._sum / count,
                histogram=self._histogram.snapshot(),
            )
