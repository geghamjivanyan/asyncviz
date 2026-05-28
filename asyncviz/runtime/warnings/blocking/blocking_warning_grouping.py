"""Per-window warning groups.

A *warning group* aggregates everything we know about one freeze
incident. One group is created when the policy decides a detector
outcome warrants surfacing; the group is then refreshed by subsequent
outcomes at the same ``window_id`` and finally closed when the freeze
window closes (or after a quiescence timeout).

The mutable working state lives on :class:`WarningGroup`; consumers
read frozen :class:`WarningGroupSnapshot` views so they never see a
half-updated record.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from asyncviz.runtime.clock.conversions import NS_PER_MS, NS_PER_SECOND
from asyncviz.runtime.monitoring.blocking import BlockingSeverity
from asyncviz.runtime.warnings.blocking.blocking_warning_state import (
    BlockingWarningGroupState,
)


@dataclass(frozen=True, slots=True)
class EscalationEntry:
    """One severity transition recorded on a group's history."""

    from_severity: str
    to_severity: str
    monotonic_ns: int
    sample_index: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_severity": self.from_severity,
            "to_severity": self.to_severity,
            "monotonic_ns": self.monotonic_ns,
            "sample_index": self.sample_index,
        }


@dataclass(frozen=True, slots=True)
class WarningGroupSnapshot:
    """Immutable snapshot of a :class:`WarningGroup`. Wire-shape stable."""

    group_id: str
    warning_id: str
    runtime_id: str
    window_id: str | None
    state: BlockingWarningGroupState
    severity: str
    peak_severity: str
    first_seen_ns: int
    last_seen_ns: int
    recovered_ns: int | None
    expired_ns: int | None
    peak_lag_ns: int
    last_lag_ns: int
    violation_count: int
    escalation_count: int
    capture_ids: tuple[int, ...]
    escalation_history: tuple[EscalationEntry, ...]
    task_id: str | None
    task_name: str | None
    coroutine_name: str | None

    @property
    def freeze_duration_ns(self) -> int:
        end = self.recovered_ns if self.recovered_ns is not None else self.last_seen_ns
        delta = end - self.first_seen_ns
        return delta if delta > 0 else 0

    @property
    def freeze_duration_ms(self) -> float:
        return self.freeze_duration_ns / NS_PER_MS

    @property
    def freeze_duration_seconds(self) -> float:
        return self.freeze_duration_ns / NS_PER_SECOND

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "warning_id": self.warning_id,
            "runtime_id": self.runtime_id,
            "window_id": self.window_id,
            "state": self.state.value,
            "severity": self.severity,
            "peak_severity": self.peak_severity,
            "first_seen_ns": self.first_seen_ns,
            "last_seen_ns": self.last_seen_ns,
            "recovered_ns": self.recovered_ns,
            "expired_ns": self.expired_ns,
            "peak_lag_ns": self.peak_lag_ns,
            "last_lag_ns": self.last_lag_ns,
            "freeze_duration_ns": self.freeze_duration_ns,
            "freeze_duration_ms": self.freeze_duration_ms,
            "violation_count": self.violation_count,
            "escalation_count": self.escalation_count,
            "capture_ids": list(self.capture_ids),
            "escalation_history": [e.to_dict() for e in self.escalation_history],
            "task_id": self.task_id,
            "task_name": self.task_name,
            "coroutine_name": self.coroutine_name,
        }


@dataclass(slots=True)
class WarningGroup:
    """Mutable per-window warning aggregation.

    Internal to the emitter. Consumers read via :meth:`snapshot`. All
    mutating methods are intentionally tiny — the orchestrator updates
    one field at a time so the lock window stays minimal.
    """

    group_id: str
    warning_id: str
    runtime_id: str
    window_id: str | None
    state: BlockingWarningGroupState
    severity: str
    peak_severity: str
    first_seen_ns: int
    last_seen_ns: int
    peak_lag_ns: int
    last_lag_ns: int
    violation_count: int
    escalation_count: int
    capture_ids: list[int] = field(default_factory=list)
    escalation_history: deque[EscalationEntry] = field(default_factory=lambda: deque(maxlen=16))
    recovered_ns: int | None = None
    expired_ns: int | None = None
    task_id: str | None = None
    task_name: str | None = None
    coroutine_name: str | None = None

    # ── transitions ──────────────────────────────────────────────────────
    def record_observation(
        self,
        *,
        severity: BlockingSeverity,
        lag_ns: int,
        monotonic_ns: int,
        sample_index: int | None,
    ) -> BlockingWarningGroupState:
        """Apply one detector outcome to this group; return the new state.

        Updates severity peaks, lag peaks, violation counter, escalation
        history when the severity crosses upward. Doesn't decide emission
        — that's the emitter's job.
        """
        self.last_seen_ns = monotonic_ns
        self.last_lag_ns = lag_ns
        self.violation_count += 1
        if lag_ns > self.peak_lag_ns:
            self.peak_lag_ns = lag_ns
        prev_peak = self.peak_severity
        sev_name = severity.name
        if _severity_rank(sev_name) > _severity_rank(self.peak_severity):
            self.peak_severity = sev_name
        if _severity_rank(sev_name) > _severity_rank(self.severity):
            self.escalation_count += 1
            self.escalation_history.append(
                EscalationEntry(
                    from_severity=self.severity,
                    to_severity=sev_name,
                    monotonic_ns=monotonic_ns,
                    sample_index=sample_index,
                )
            )
            self.severity = sev_name
            self.state = BlockingWarningGroupState.ESCALATING
            return self.state
        # Same-or-lower severity: refresh.
        if self.state in (
            BlockingWarningGroupState.OPENED,
            BlockingWarningGroupState.ESCALATING,
        ):
            self.state = BlockingWarningGroupState.ACTIVE
        # Severity field always reflects the latest *observed* severity
        # so consumers querying ``group.severity`` see what's happening
        # *now*, not the historical peak. ``peak_severity`` carries the
        # historical peak independently.
        self.severity = sev_name
        # peak unchanged — keep prev_peak.
        del prev_peak
        return self.state

    def record_capture(self, capture_id: int) -> None:
        self.capture_ids.append(capture_id)

    def mark_recovered(self, *, monotonic_ns: int) -> None:
        self.state = BlockingWarningGroupState.RECOVERED
        self.recovered_ns = monotonic_ns

    def mark_expired(self, *, monotonic_ns: int) -> None:
        self.state = BlockingWarningGroupState.EXPIRED
        self.expired_ns = monotonic_ns

    def attach_task(
        self,
        *,
        task_id: str | None,
        task_name: str | None,
        coroutine_name: str | None,
    ) -> None:
        # Only fill empty slots — once a group is correlated with a
        # task, additional captures shouldn't overwrite. Same task may
        # appear in multiple captures.
        if self.task_id is None and task_id is not None:
            self.task_id = task_id
        if self.task_name is None and task_name is not None:
            self.task_name = task_name
        if self.coroutine_name is None and coroutine_name is not None:
            self.coroutine_name = coroutine_name

    def snapshot(self) -> WarningGroupSnapshot:
        return WarningGroupSnapshot(
            group_id=self.group_id,
            warning_id=self.warning_id,
            runtime_id=self.runtime_id,
            window_id=self.window_id,
            state=self.state,
            severity=self.severity,
            peak_severity=self.peak_severity,
            first_seen_ns=self.first_seen_ns,
            last_seen_ns=self.last_seen_ns,
            recovered_ns=self.recovered_ns,
            expired_ns=self.expired_ns,
            peak_lag_ns=self.peak_lag_ns,
            last_lag_ns=self.last_lag_ns,
            violation_count=self.violation_count,
            escalation_count=self.escalation_count,
            capture_ids=tuple(self.capture_ids),
            escalation_history=tuple(self.escalation_history),
            task_id=self.task_id,
            task_name=self.task_name,
            coroutine_name=self.coroutine_name,
        )


def _severity_rank(name: str) -> int:
    """Ordering rank for severity name comparisons.

    Local helper so the grouping module doesn't import the
    ``BlockingSeverity`` enum into its hot path (the enum lookup is
    O(1) but the equality dance gets noisy).
    """
    ranks = {"NONE": 0, "WARNING": 1, "CRITICAL": 2, "FREEZE": 3}
    return ranks.get(name, 0)


class WarningGroupRegistry:
    """Indexed collection of :class:`WarningGroup` objects.

    Thread-safe — the emitter dispatches detector + capture events on
    the asyncio loop today, but tests + future cross-thread consumers
    may read concurrently.
    """

    def __init__(self, *, recent_capacity: int = 64) -> None:
        if recent_capacity <= 0:
            raise ValueError(f"recent_capacity must be > 0 (got {recent_capacity})")
        self._lock = threading.Lock()
        self._active: dict[str, WarningGroup] = {}
        self._recent: deque[WarningGroupSnapshot] = deque(maxlen=recent_capacity)
        self._by_window: dict[str, str] = {}  # window_id → group_id
        self._sequence = 0

    def __len__(self) -> int:
        with self._lock:
            return len(self._active)

    def next_sequence(self) -> int:
        with self._lock:
            self._sequence += 1
            return self._sequence

    def add(self, group: WarningGroup) -> None:
        with self._lock:
            self._active[group.group_id] = group
            if group.window_id is not None:
                self._by_window[group.window_id] = group.group_id

    def find_by_group_id(self, group_id: str) -> WarningGroup | None:
        with self._lock:
            return self._active.get(group_id)

    def find_by_window_id(self, window_id: str) -> WarningGroup | None:
        with self._lock:
            gid = self._by_window.get(window_id)
            return self._active.get(gid) if gid is not None else None

    def finalize(self, group: WarningGroup) -> None:
        """Move the group from the active map to the recent ring."""
        with self._lock:
            self._active.pop(group.group_id, None)
            if (
                group.window_id is not None
                and self._by_window.get(group.window_id) == group.group_id
            ):
                self._by_window.pop(group.window_id, None)
            self._recent.append(group.snapshot())

    def active_snapshots(self) -> tuple[WarningGroupSnapshot, ...]:
        with self._lock:
            return tuple(g.snapshot() for g in self._active.values())

    def recent_snapshots(self) -> tuple[WarningGroupSnapshot, ...]:
        with self._lock:
            return tuple(self._recent)

    def reset(self) -> None:
        with self._lock:
            self._active.clear()
            self._by_window.clear()
            self._recent.clear()
            self._sequence = 0
