"""Replay frame primitives — :class:`ReplayFrame` + adapters from runtime events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models import to_dict


@dataclass(frozen=True, slots=True)
class ReplayFrame:
    """One immutable event captured in the replay log.

    Distinct from :class:`asyncviz.runtime.queue.QueuedEvent` because:

    * The frame carries an already-serialized ``payload`` (JSON-safe) so
      the bridge can broadcast directly without re-serializing on every
      replay request.
    * Frame fields are flat for cheap sequence-indexed lookup; reads
      don't have to walk the embedded ``RuntimeEvent``.

    Frames are produced once at append time and never mutated.
    """

    sequence: int
    event_id: str
    event_type: str
    monotonic_ns: int
    wall_seconds: float
    runtime_id: str
    task_id: str | None
    parent_task_id: str | None
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "monotonic_ns": self.monotonic_ns,
            "wall_seconds": self.wall_seconds,
            "runtime_id": self.runtime_id,
            "task_id": self.task_id,
            "parent_task_id": self.parent_task_id,
            "payload": dict(self.payload),
        }


def frame_from_event(event: RuntimeEvent, *, sequence: int) -> ReplayFrame:
    """Materialize a :class:`ReplayFrame` from one event + its allocated sequence."""
    payload = to_dict(event)
    return ReplayFrame(
        sequence=sequence,
        event_id=str(event.event_id),
        event_type=event.event_type,
        monotonic_ns=event.monotonic_ns,
        wall_seconds=event.timestamp,
        runtime_id=str(event.runtime_id),
        task_id=getattr(event, "task_id", None)
        if isinstance(getattr(event, "task_id", None), str)
        else None,
        parent_task_id=getattr(event, "parent_task_id", None)
        if isinstance(getattr(event, "parent_task_id", None), str)
        else None,
        payload=payload,
    )
