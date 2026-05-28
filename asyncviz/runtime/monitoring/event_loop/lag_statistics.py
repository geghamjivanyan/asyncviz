"""Rolling-window aggregator over lag measurements.

The aggregator maintains:

* min / max / mean / sum over the window
* peak lag over the lifetime of the monitor (never decreases)
* percentiles via a simple sorted-copy strategy (window is small —
  default 256 — so O(N log N) per query is negligible and avoids the
  complexity of a streaming digest)
* consecutive-spike + freeze-duration tracking

Replay-safe: every output is a deterministic function of the sequence of
``observe()`` calls. No timestamps are read internally.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass

from asyncviz.runtime.clock.conversions import NS_PER_MS, NS_PER_SECOND
from asyncviz.runtime.monitoring.event_loop.lag_measurement import LagMeasurement
from asyncviz.runtime.monitoring.event_loop.lag_thresholds import LagSeverity


@dataclass(frozen=True, slots=True)
class LagStatisticsSnapshot:
    """Immutable rolling-window view.

    All ``*_ns`` fields are integer nanoseconds; the matching ``_seconds``
    variants are derived once at snapshot time for display surfaces.
    """

    sample_count: int
    window_capacity: int
    window_filled: int
    sum_ns: int
    min_ns: int
    max_ns: int
    mean_ns: int
    p50_ns: int
    p95_ns: int
    p99_ns: int
    peak_ns: int
    last_ns: int
    consecutive_warning_count: int
    consecutive_critical_count: int
    consecutive_freeze_count: int
    freeze_segments: int
    last_freeze_duration_ns: int
    longest_freeze_duration_ns: int

    @property
    def mean_seconds(self) -> float:
        return self.mean_ns / NS_PER_SECOND

    @property
    def mean_ms(self) -> float:
        return self.mean_ns / NS_PER_MS

    @property
    def p95_ms(self) -> float:
        return self.p95_ns / NS_PER_MS

    @property
    def p99_ms(self) -> float:
        return self.p99_ns / NS_PER_MS

    @property
    def peak_ms(self) -> float:
        return self.peak_ns / NS_PER_MS

    def to_dict(self) -> dict[str, object]:
        return {
            "sample_count": self.sample_count,
            "window_capacity": self.window_capacity,
            "window_filled": self.window_filled,
            "sum_ns": self.sum_ns,
            "min_ns": self.min_ns,
            "max_ns": self.max_ns,
            "mean_ns": self.mean_ns,
            "mean_ms": self.mean_ms,
            "p50_ns": self.p50_ns,
            "p95_ns": self.p95_ns,
            "p95_ms": self.p95_ms,
            "p99_ns": self.p99_ns,
            "p99_ms": self.p99_ms,
            "peak_ns": self.peak_ns,
            "peak_ms": self.peak_ms,
            "last_ns": self.last_ns,
            "consecutive_warning_count": self.consecutive_warning_count,
            "consecutive_critical_count": self.consecutive_critical_count,
            "consecutive_freeze_count": self.consecutive_freeze_count,
            "freeze_segments": self.freeze_segments,
            "last_freeze_duration_ns": self.last_freeze_duration_ns,
            "longest_freeze_duration_ns": self.longest_freeze_duration_ns,
        }


class LagStatistics:
    """Bounded rolling-window aggregator over lag-ns observations.

    Thread-safe: the deque + counters are guarded by a single lock.
    Reading the deque is O(1); :meth:`snapshot` copies + sorts the
    window once for percentiles (cheap for the default 256 capacity).
    """

    def __init__(self, *, window: int) -> None:
        if window <= 0:
            raise ValueError(f"window must be > 0 (got {window})")
        self._window = window
        self._lock = threading.Lock()
        self._values: deque[int] = deque(maxlen=window)
        self._sum = 0
        self._sample_count = 0
        self._peak = 0
        self._last = 0
        self._consecutive_warning = 0
        self._consecutive_critical = 0
        self._consecutive_freeze = 0
        self._freeze_segments = 0
        self._in_freeze = False
        self._current_freeze_ns = 0
        self._last_freeze_ns = 0
        self._longest_freeze_ns = 0

    @property
    def window(self) -> int:
        return self._window

    def reset(self) -> None:
        with self._lock:
            self._values.clear()
            self._sum = 0
            self._sample_count = 0
            self._peak = 0
            self._last = 0
            self._consecutive_warning = 0
            self._consecutive_critical = 0
            self._consecutive_freeze = 0
            self._freeze_segments = 0
            self._in_freeze = False
            self._current_freeze_ns = 0
            self._last_freeze_ns = 0
            self._longest_freeze_ns = 0

    def observe(self, measurement: LagMeasurement, severity: LagSeverity) -> None:
        """Record one measurement + its evaluated severity.

        Severity is passed in (rather than re-derived) so the threshold
        policy stays the single source of truth and statistics tracks
        whatever the monitor actually flagged.
        """
        lag_ns = measurement.lag_ns
        with self._lock:
            if len(self._values) == self._window:
                # Evict before adding so the rolling sum stays accurate.
                self._sum -= self._values[0]
            self._values.append(lag_ns)
            self._sum += lag_ns
            self._sample_count += 1
            self._last = lag_ns
            if lag_ns > self._peak:
                self._peak = lag_ns
            self._update_consecutive(severity, lag_ns)

    def _update_consecutive(self, severity: LagSeverity, lag_ns: int) -> None:
        if severity >= LagSeverity.WARNING:
            self._consecutive_warning += 1
        else:
            self._consecutive_warning = 0
        if severity >= LagSeverity.CRITICAL:
            self._consecutive_critical += 1
        else:
            self._consecutive_critical = 0
        if severity >= LagSeverity.FREEZE:
            self._consecutive_freeze += 1
            if not self._in_freeze:
                self._in_freeze = True
                self._freeze_segments += 1
                self._current_freeze_ns = lag_ns
            else:
                self._current_freeze_ns += lag_ns
            self._last_freeze_ns = self._current_freeze_ns
            if self._current_freeze_ns > self._longest_freeze_ns:
                self._longest_freeze_ns = self._current_freeze_ns
        else:
            self._consecutive_freeze = 0
            self._in_freeze = False
            self._current_freeze_ns = 0

    def snapshot(self) -> LagStatisticsSnapshot:
        with self._lock:
            filled = len(self._values)
            if filled == 0:
                return LagStatisticsSnapshot(
                    sample_count=self._sample_count,
                    window_capacity=self._window,
                    window_filled=0,
                    sum_ns=0,
                    min_ns=0,
                    max_ns=0,
                    mean_ns=0,
                    p50_ns=0,
                    p95_ns=0,
                    p99_ns=0,
                    peak_ns=self._peak,
                    last_ns=self._last,
                    consecutive_warning_count=self._consecutive_warning,
                    consecutive_critical_count=self._consecutive_critical,
                    consecutive_freeze_count=self._consecutive_freeze,
                    freeze_segments=self._freeze_segments,
                    last_freeze_duration_ns=self._last_freeze_ns,
                    longest_freeze_duration_ns=self._longest_freeze_ns,
                )
            sorted_values = sorted(self._values)
            mean_ns = self._sum // filled
            return LagStatisticsSnapshot(
                sample_count=self._sample_count,
                window_capacity=self._window,
                window_filled=filled,
                sum_ns=self._sum,
                min_ns=sorted_values[0],
                max_ns=sorted_values[-1],
                mean_ns=mean_ns,
                p50_ns=_percentile(sorted_values, 0.50),
                p95_ns=_percentile(sorted_values, 0.95),
                p99_ns=_percentile(sorted_values, 0.99),
                peak_ns=self._peak,
                last_ns=self._last,
                consecutive_warning_count=self._consecutive_warning,
                consecutive_critical_count=self._consecutive_critical,
                consecutive_freeze_count=self._consecutive_freeze,
                freeze_segments=self._freeze_segments,
                last_freeze_duration_ns=self._last_freeze_ns,
                longest_freeze_duration_ns=self._longest_freeze_ns,
            )


def _percentile(sorted_values: list[int], q: float) -> int:
    """Nearest-rank percentile on a pre-sorted list.

    Standard "rank = ceil(q * N)" formulation, clamped at the bounds.
    Returns an integer — the rest of the system stores lag in
    nanoseconds; we never want to introduce float drift here.
    """
    if not sorted_values:
        return 0
    n = len(sorted_values)
    if q <= 0:
        return sorted_values[0]
    if q >= 1:
        return sorted_values[-1]
    # Nearest-rank: ceil(q * n) - 1 (0-indexed).
    rank = int(q * n)
    if rank == 0:
        rank = 1
    # rank in [1, n], convert to 0-indexed:
    idx = min(rank, n) - 1
    return sorted_values[idx]
