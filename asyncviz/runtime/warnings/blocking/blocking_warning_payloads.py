"""Canonical wire payload for emitted blocking warnings.

The emitter never wraps raw :class:`WarningGroupSnapshot` objects in
events. Instead it composes one :class:`BlockingWarningPayload` per
lifecycle transition — that gives downstream consumers a uniform shape
regardless of which engine surface (events / API / replay) they're
reading.

Payload guarantees:

* deterministic field order (frozen dataclass).
* bounded size (capture references are id-only).
* no clock reads — every timestamp comes from the group state.
* JSON-safe — every field is either a primitive, a list, or a dict.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from asyncviz.runtime.clock.conversions import NS_PER_MS
from asyncviz.runtime.warnings.blocking.blocking_warning_grouping import (
    WarningGroupSnapshot,
)


@dataclass(frozen=True, slots=True)
class BlockingWarningPayload:
    """The wire payload embedded in every blocking-warning event."""

    warning_id: str
    group_id: str
    runtime_id: str
    window_id: str | None
    state: str
    severity: str
    peak_severity: str
    first_seen_ns: int
    last_seen_ns: int
    recovered_ns: int | None
    expired_ns: int | None
    freeze_duration_ns: int
    peak_lag_ns: int
    last_lag_ns: int
    violation_count: int
    escalation_count: int
    capture_ids: tuple[int, ...]
    escalation_history: tuple[dict[str, Any], ...]
    task_id: str | None
    task_name: str | None
    coroutine_name: str | None
    transition: str
    sequence: int

    @property
    def freeze_duration_ms(self) -> float:
        return self.freeze_duration_ns / NS_PER_MS

    def to_dict(self) -> dict[str, Any]:
        return {
            "warning_id": self.warning_id,
            "group_id": self.group_id,
            "runtime_id": self.runtime_id,
            "window_id": self.window_id,
            "state": self.state,
            "severity": self.severity,
            "peak_severity": self.peak_severity,
            "first_seen_ns": self.first_seen_ns,
            "last_seen_ns": self.last_seen_ns,
            "recovered_ns": self.recovered_ns,
            "expired_ns": self.expired_ns,
            "freeze_duration_ns": self.freeze_duration_ns,
            "freeze_duration_ms": self.freeze_duration_ms,
            "peak_lag_ns": self.peak_lag_ns,
            "last_lag_ns": self.last_lag_ns,
            "violation_count": self.violation_count,
            "escalation_count": self.escalation_count,
            "capture_ids": list(self.capture_ids),
            "escalation_history": list(self.escalation_history),
            "task_id": self.task_id,
            "task_name": self.task_name,
            "coroutine_name": self.coroutine_name,
            "transition": self.transition,
            "sequence": self.sequence,
        }


def build_payload(
    *,
    snapshot: WarningGroupSnapshot,
    transition: str,
    sequence: int,
) -> BlockingWarningPayload:
    """Compose a :class:`BlockingWarningPayload` from a group snapshot.

    ``transition`` is the lifecycle event label ("opened" / "escalated"
    / "active" / "recovered" / "expired"). The sequence is the
    emitter's local monotonic id; consumers can dedup on
    ``(warning_id, sequence)``.
    """
    return BlockingWarningPayload(
        warning_id=snapshot.warning_id,
        group_id=snapshot.group_id,
        runtime_id=snapshot.runtime_id,
        window_id=snapshot.window_id,
        state=snapshot.state.value,
        severity=snapshot.severity,
        peak_severity=snapshot.peak_severity,
        first_seen_ns=snapshot.first_seen_ns,
        last_seen_ns=snapshot.last_seen_ns,
        recovered_ns=snapshot.recovered_ns,
        expired_ns=snapshot.expired_ns,
        freeze_duration_ns=snapshot.freeze_duration_ns,
        peak_lag_ns=snapshot.peak_lag_ns,
        last_lag_ns=snapshot.last_lag_ns,
        violation_count=snapshot.violation_count,
        escalation_count=snapshot.escalation_count,
        capture_ids=snapshot.capture_ids,
        escalation_history=tuple(e.to_dict() for e in snapshot.escalation_history),
        task_id=snapshot.task_id,
        task_name=snapshot.task_name,
        coroutine_name=snapshot.coroutine_name,
        transition=transition,
        sequence=sequence,
    )
