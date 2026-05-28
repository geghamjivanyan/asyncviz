"""Window-level statistical aggregation.

Tracks aggregate metrics over the *lifetime* of the detector:

* total / longest / mean window duration (nanoseconds)
* total / max window violation count
* per-severity peak windows
* per-severity total violation count

Distinct from :class:`BlockingMetrics`, which tracks counters about
events the detector produced. This module tracks counters about the
runtime *phenomena* the detector observed.

All ingestion paths are :meth:`observe_*` methods so the detector can
funnel transitions in without re-deriving anything; the lock is held
for one short critical section per call.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from asyncviz.runtime.clock.conversions import NS_PER_MS, NS_PER_SECOND
from asyncviz.runtime.monitoring.blocking.blocking_classifier import BlockingSeverity
from asyncviz.runtime.monitoring.blocking.blocking_windows import BlockingWindowSnapshot


@dataclass(frozen=True, slots=True)
class BlockingStatisticsSnapshot:
    """Immutable lifetime statistics over windows + violations."""

    windows_seen: int
    closed_windows: int
    total_window_duration_ns: int
    longest_window_duration_ns: int
    longest_window_id: str | None
    mean_window_duration_ns: int
    max_violation_count_in_window: int
    total_violations_in_windows: int
    peak_lag_ns_lifetime: int
    peak_severity_lifetime: BlockingSeverity
    freeze_windows: int
    critical_windows: int
    warning_windows: int

    @property
    def total_window_duration_seconds(self) -> float:
        return self.total_window_duration_ns / NS_PER_SECOND

    @property
    def longest_window_duration_ms(self) -> float:
        return self.longest_window_duration_ns / NS_PER_MS

    @property
    def mean_window_duration_ms(self) -> float:
        return self.mean_window_duration_ns / NS_PER_MS

    def to_dict(self) -> dict[str, Any]:
        return {
            "windows_seen": self.windows_seen,
            "closed_windows": self.closed_windows,
            "total_window_duration_ns": self.total_window_duration_ns,
            "total_window_duration_seconds": self.total_window_duration_seconds,
            "longest_window_duration_ns": self.longest_window_duration_ns,
            "longest_window_duration_ms": self.longest_window_duration_ms,
            "longest_window_id": self.longest_window_id,
            "mean_window_duration_ns": self.mean_window_duration_ns,
            "mean_window_duration_ms": self.mean_window_duration_ms,
            "max_violation_count_in_window": self.max_violation_count_in_window,
            "total_violations_in_windows": self.total_violations_in_windows,
            "peak_lag_ns_lifetime": self.peak_lag_ns_lifetime,
            "peak_severity_lifetime": self.peak_severity_lifetime.name,
            "freeze_windows": self.freeze_windows,
            "critical_windows": self.critical_windows,
            "warning_windows": self.warning_windows,
        }


class BlockingStatistics:
    """Lifetime aggregates over windows.

    Open windows are not double-counted: each window contributes once,
    at close time. ``observe_window_opened`` exists so callers can also
    track windows-seen for parity even before close.
    """

    __slots__ = (
        "_closed_windows",
        "_critical_windows",
        "_freeze_windows",
        "_lock",
        "_longest_window_duration_ns",
        "_longest_window_id",
        "_max_violation_count_in_window",
        "_peak_lag_ns_lifetime",
        "_peak_severity_lifetime",
        "_total_violations_in_windows",
        "_total_window_duration_ns",
        "_warning_windows",
        "_windows_seen",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows_seen = 0
        self._closed_windows = 0
        self._total_window_duration_ns = 0
        self._longest_window_duration_ns = 0
        self._longest_window_id: str | None = None
        self._max_violation_count_in_window = 0
        self._total_violations_in_windows = 0
        self._peak_lag_ns_lifetime = 0
        self._peak_severity_lifetime: BlockingSeverity = BlockingSeverity.NONE
        self._warning_windows = 0
        self._critical_windows = 0
        self._freeze_windows = 0

    def reset(self) -> None:
        with self._lock:
            self._windows_seen = 0
            self._closed_windows = 0
            self._total_window_duration_ns = 0
            self._longest_window_duration_ns = 0
            self._longest_window_id = None
            self._max_violation_count_in_window = 0
            self._total_violations_in_windows = 0
            self._peak_lag_ns_lifetime = 0
            self._peak_severity_lifetime = BlockingSeverity.NONE
            self._warning_windows = 0
            self._critical_windows = 0
            self._freeze_windows = 0

    def observe_window_opened(self) -> None:
        with self._lock:
            self._windows_seen += 1

    def observe_window_closed(self, window: BlockingWindowSnapshot) -> None:
        with self._lock:
            self._closed_windows += 1
            dur = window.duration_ns
            self._total_window_duration_ns += dur
            if dur > self._longest_window_duration_ns:
                self._longest_window_duration_ns = dur
                self._longest_window_id = window.window_id
            if window.violation_count > self._max_violation_count_in_window:
                self._max_violation_count_in_window = window.violation_count
            self._total_violations_in_windows += window.violation_count
            if window.peak_lag_ns > self._peak_lag_ns_lifetime:
                self._peak_lag_ns_lifetime = window.peak_lag_ns
            if window.peak_severity > self._peak_severity_lifetime:
                self._peak_severity_lifetime = window.peak_severity
            if window.peak_severity is BlockingSeverity.FREEZE:
                self._freeze_windows += 1
            elif window.peak_severity is BlockingSeverity.CRITICAL:
                self._critical_windows += 1
            elif window.peak_severity is BlockingSeverity.WARNING:
                self._warning_windows += 1

    def observe_peak_lag(self, lag_ns: int) -> None:
        """Update the lifetime peak without waiting for a window close.

        Useful for samples that don't open a window (e.g. an isolated
        warning below ``window_open_severity``) but still carry the
        lifetime peak.
        """
        with self._lock:
            if lag_ns > self._peak_lag_ns_lifetime:
                self._peak_lag_ns_lifetime = lag_ns

    def snapshot(self) -> BlockingStatisticsSnapshot:
        with self._lock:
            mean = (
                self._total_window_duration_ns // self._closed_windows
                if self._closed_windows > 0
                else 0
            )
            return BlockingStatisticsSnapshot(
                windows_seen=self._windows_seen,
                closed_windows=self._closed_windows,
                total_window_duration_ns=self._total_window_duration_ns,
                longest_window_duration_ns=self._longest_window_duration_ns,
                longest_window_id=self._longest_window_id,
                mean_window_duration_ns=mean,
                max_violation_count_in_window=self._max_violation_count_in_window,
                total_violations_in_windows=self._total_violations_in_windows,
                peak_lag_ns_lifetime=self._peak_lag_ns_lifetime,
                peak_severity_lifetime=self._peak_severity_lifetime,
                freeze_windows=self._freeze_windows,
                critical_windows=self._critical_windows,
                warning_windows=self._warning_windows,
            )
