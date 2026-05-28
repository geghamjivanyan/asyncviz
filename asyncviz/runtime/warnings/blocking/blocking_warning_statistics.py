"""Lifetime statistics over emitted warning groups.

Distinct from :class:`BlockingWarningMetrics` (engine self-counters) —
this module tracks aggregates over the *content* of the warnings: peak
freeze duration ever observed, longest active group, severity breakdown,
top-N coroutine names by warning count, etc.

Useful for the dashboard's "what's been going wrong?" panel without
forcing every consumer to scan the replay log.
"""

from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass
from typing import Any

from asyncviz.runtime.clock.conversions import NS_PER_MS, NS_PER_SECOND
from asyncviz.runtime.warnings.blocking.blocking_warning_grouping import (
    WarningGroupSnapshot,
)


@dataclass(frozen=True, slots=True)
class TopCoroutineStat:
    coroutine_name: str
    warning_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "coroutine_name": self.coroutine_name,
            "warning_count": self.warning_count,
        }


@dataclass(frozen=True, slots=True)
class BlockingWarningStatisticsSnapshot:
    groups_seen: int
    groups_recovered: int
    groups_expired: int
    groups_by_peak_severity: dict[str, int]
    total_freeze_duration_ns: int
    longest_freeze_duration_ns: int
    longest_freeze_group_id: str | None
    mean_freeze_duration_ns: int
    peak_lag_ns: int
    total_captures_correlated: int
    top_coroutines: tuple[TopCoroutineStat, ...]

    @property
    def total_freeze_duration_seconds(self) -> float:
        return self.total_freeze_duration_ns / NS_PER_SECOND

    @property
    def longest_freeze_duration_ms(self) -> float:
        return self.longest_freeze_duration_ns / NS_PER_MS

    def to_dict(self) -> dict[str, Any]:
        return {
            "groups_seen": self.groups_seen,
            "groups_recovered": self.groups_recovered,
            "groups_expired": self.groups_expired,
            "groups_by_peak_severity": dict(self.groups_by_peak_severity),
            "total_freeze_duration_ns": self.total_freeze_duration_ns,
            "total_freeze_duration_seconds": self.total_freeze_duration_seconds,
            "longest_freeze_duration_ns": self.longest_freeze_duration_ns,
            "longest_freeze_duration_ms": self.longest_freeze_duration_ms,
            "longest_freeze_group_id": self.longest_freeze_group_id,
            "mean_freeze_duration_ns": self.mean_freeze_duration_ns,
            "peak_lag_ns": self.peak_lag_ns,
            "total_captures_correlated": self.total_captures_correlated,
            "top_coroutines": [t.to_dict() for t in self.top_coroutines],
        }


class BlockingWarningStatistics:
    """Aggregate stats over finalized warning groups."""

    DEFAULT_TOP_COROUTINE_LIMIT: int = 5

    __slots__ = (
        "_by_peak_severity",
        "_coroutine_counter",
        "_groups_expired",
        "_groups_recovered",
        "_groups_seen",
        "_lock",
        "_longest_freeze_duration_ns",
        "_longest_freeze_group_id",
        "_peak_lag_ns",
        "_top_coroutine_limit",
        "_total_captures_correlated",
        "_total_freeze_duration_ns",
    )

    def __init__(self, *, top_coroutine_limit: int = DEFAULT_TOP_COROUTINE_LIMIT) -> None:
        if top_coroutine_limit <= 0:
            raise ValueError(f"top_coroutine_limit must be > 0 (got {top_coroutine_limit})")
        self._lock = threading.Lock()
        self._top_coroutine_limit = top_coroutine_limit
        self._groups_seen = 0
        self._groups_recovered = 0
        self._groups_expired = 0
        self._by_peak_severity: Counter[str] = Counter()
        self._total_freeze_duration_ns = 0
        self._longest_freeze_duration_ns = 0
        self._longest_freeze_group_id: str | None = None
        self._peak_lag_ns = 0
        self._total_captures_correlated = 0
        self._coroutine_counter: Counter[str] = Counter()

    def reset(self) -> None:
        with self._lock:
            self._groups_seen = 0
            self._groups_recovered = 0
            self._groups_expired = 0
            self._by_peak_severity.clear()
            self._total_freeze_duration_ns = 0
            self._longest_freeze_duration_ns = 0
            self._longest_freeze_group_id = None
            self._peak_lag_ns = 0
            self._total_captures_correlated = 0
            self._coroutine_counter.clear()

    def observe_group_opened(self, snap: WarningGroupSnapshot) -> None:
        with self._lock:
            self._groups_seen += 1
            self._by_peak_severity[snap.peak_severity] += 1
            if snap.peak_lag_ns > self._peak_lag_ns:
                self._peak_lag_ns = snap.peak_lag_ns

    def observe_group_recovered(self, snap: WarningGroupSnapshot) -> None:
        with self._lock:
            self._groups_recovered += 1
            self._roll_finalize(snap)

    def observe_group_expired(self, snap: WarningGroupSnapshot) -> None:
        with self._lock:
            self._groups_expired += 1
            self._roll_finalize(snap)

    def observe_capture_correlated(self) -> None:
        with self._lock:
            self._total_captures_correlated += 1

    def observe_coroutine(self, coroutine_name: str | None) -> None:
        if not coroutine_name:
            return
        with self._lock:
            self._coroutine_counter[coroutine_name] += 1

    def _roll_finalize(self, snap: WarningGroupSnapshot) -> None:
        dur = snap.freeze_duration_ns
        self._total_freeze_duration_ns += dur
        if dur > self._longest_freeze_duration_ns:
            self._longest_freeze_duration_ns = dur
            self._longest_freeze_group_id = snap.group_id
        if snap.peak_lag_ns > self._peak_lag_ns:
            self._peak_lag_ns = snap.peak_lag_ns
        if snap.peak_severity not in self._by_peak_severity:
            self._by_peak_severity[snap.peak_severity] += 1

    def snapshot(self) -> BlockingWarningStatisticsSnapshot:
        with self._lock:
            count = self._groups_recovered + self._groups_expired
            mean = self._total_freeze_duration_ns // count if count > 0 else 0
            top = self._coroutine_counter.most_common(self._top_coroutine_limit)
            return BlockingWarningStatisticsSnapshot(
                groups_seen=self._groups_seen,
                groups_recovered=self._groups_recovered,
                groups_expired=self._groups_expired,
                groups_by_peak_severity=dict(self._by_peak_severity),
                total_freeze_duration_ns=self._total_freeze_duration_ns,
                longest_freeze_duration_ns=self._longest_freeze_duration_ns,
                longest_freeze_group_id=self._longest_freeze_group_id,
                mean_freeze_duration_ns=mean,
                peak_lag_ns=self._peak_lag_ns,
                total_captures_correlated=self._total_captures_correlated,
                top_coroutines=tuple(
                    TopCoroutineStat(coroutine_name=k, warning_count=v) for k, v in top
                ),
            )
