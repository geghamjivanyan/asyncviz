"""Event / metric → detector-trigger normalization."""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models import (
    TaskCancelledEvent,
    TaskCompletedEvent,
    TaskFailedEvent,
)
from asyncviz.runtime.events.models.enums import WarningSeverity


@dataclass(frozen=True, slots=True)
class WarningTrigger:
    """One detector-trigger candidate.

    Synthesized from a runtime event so detectors can read it without
    re-walking the event class hierarchy. ``warning_type`` is the
    detector's stable name; ``warning_key`` is the dedup primary key.
    """

    warning_type: str
    warning_key: str
    severity: WarningSeverity
    message: str
    detector: str
    sequence: int | None
    monotonic_ns: int
    wall_seconds: float
    related_task_ids: tuple[str, ...]
    lineage_root_id: str | None
    metadata: dict[str, object]


def is_terminal_task_event(event: RuntimeEvent) -> bool:
    """Whether ``event`` finalizes a task (one of completed / cancelled / failed)."""
    return isinstance(event, (TaskCompletedEvent, TaskCancelledEvent, TaskFailedEvent))
