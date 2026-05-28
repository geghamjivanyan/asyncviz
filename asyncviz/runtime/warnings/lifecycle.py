"""Per-warning mutable working state."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from asyncviz.runtime.events.models.enums import WarningSeverity


@dataclass(slots=True)
class WarningLifecycle:
    """Mutable per-warning working set.

    Stored in :class:`RuntimeWarningManager._lifecycles` keyed by
    ``warning_key`` (the dedup primary key). The manager produces a fresh
    :class:`ActiveWarning` Pydantic value from this on each snapshot.

    Field order is the working-set order, not the wire order — keep the
    Pydantic model's field order separately (in ``models.py``).
    """

    warning_id: str
    warning_key: str
    warning_type: str
    severity: WarningSeverity
    detector: str
    message: str
    created_sequence: int | None
    created_monotonic_ns: int
    created_at_wall: float
    last_observed_sequence: int | None
    last_observed_monotonic_ns: int
    last_observed_wall: float
    occurrence_count: int = 1
    resolved: bool = False
    resolved_sequence: int | None = None
    resolved_monotonic_ns: int | None = None
    resolved_at_wall: float | None = None
    expired: bool = False
    related_task_ids: list[str] = field(default_factory=list)
    lineage_root_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    runtime_id: str | None = None

    def mark_observed(
        self,
        *,
        sequence: int | None,
        monotonic_ns: int,
        wall_seconds: float,
        message: str | None = None,
    ) -> None:
        """Bump the dedup counters / timestamps for a repeat trigger."""
        self.occurrence_count += 1
        if sequence is not None:
            self.last_observed_sequence = sequence
        self.last_observed_monotonic_ns = monotonic_ns
        self.last_observed_wall = wall_seconds
        if message is not None:
            self.message = message

    def mark_resolved(
        self,
        *,
        sequence: int | None,
        monotonic_ns: int,
        wall_seconds: float,
    ) -> None:
        """Mark the warning as resolved. Idempotent."""
        if self.resolved:
            return
        self.resolved = True
        self.resolved_sequence = sequence
        self.resolved_monotonic_ns = monotonic_ns
        self.resolved_at_wall = wall_seconds

    def mark_expired(
        self,
        *,
        monotonic_ns: int,
        wall_seconds: float,
    ) -> None:
        """Mark the warning as expired (auto-resolution after silence)."""
        if self.expired:
            return
        self.expired = True
        if not self.resolved:
            self.resolved = True
            self.resolved_sequence = None
            self.resolved_monotonic_ns = monotonic_ns
            self.resolved_at_wall = wall_seconds


def fresh_warning_id() -> str:
    """Stable-style id for use in new warnings. uuid4 for non-replay scenarios."""
    return uuid.uuid4().hex
