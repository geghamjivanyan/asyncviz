"""Runtime event models for ``asyncio.gather`` instrumentation.

Schema notes:

* Every event carries the gather's identity (``gather_id``,
  ``parent_task_id``, ``child_count``) so a consumer can resolve the
  await group without keeping the registry in scope.
* ``snapshot`` captures the gather's progress at event time
  (completed / pending / cancelled / failed). Frontends can chart it
  inline or descend into the dict for full detail.
* Per-child events (``child_attached``, ``child_completed``) carry the
  ``child_task_id`` so a future await-dependency graph can plot
  parent-to-child edges directly off the wire.
* Payloads never reference coroutine objects or exception payloads;
  only enums + integers + ids. Replay safety is the same property
  the task + queue + semaphore event families promise.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from asyncviz.runtime.events.models.base import RuntimeEvent


class _GatherEventBase(RuntimeEvent):
    """Shared envelope fields for every gather event."""

    gather_id: str
    parent_task_id: str | None = None
    child_count: int = 0
    snapshot: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GatherCreatedEvent(_GatherEventBase):
    """Fired at the start of an instrumented ``asyncio.gather`` call."""

    event_type: Literal["asyncio.gather.created"] = "asyncio.gather.created"
    child_task_ids: tuple[str, ...] = ()
    return_exceptions: bool = False


class GatherChildAttachedEvent(_GatherEventBase):
    """Fired once per child after the gather has wired it up.

    Lets a dependency-graph consumer build parent→child edges without
    having to wait for the gather to complete (a long-running gather
    on a 1000-child fanout would otherwise be invisible until done)."""

    event_type: Literal["asyncio.gather.child.attached"] = "asyncio.gather.child.attached"
    child_task_id: str
    child_index: int = 0


class GatherWaitStartedEvent(_GatherEventBase):
    """Fired immediately after all children are attached + the underlying
    gather future is created. ``parent_task_id`` is now actively awaiting
    on the gather."""

    event_type: Literal["asyncio.gather.wait.started"] = "asyncio.gather.wait.started"


class GatherChildCompletedEvent(_GatherEventBase):
    """Fired when one child transitions to done."""

    event_type: Literal["asyncio.gather.child.completed"] = "asyncio.gather.child.completed"
    child_task_id: str
    child_index: int = 0
    cancelled: bool = False
    """``True`` when the child finished via cancellation."""
    failed: bool = False
    """``True`` when the child finished by raising (non-cancellation)."""
    completed_count: int = 0
    """Cumulative completed-children count after this event applies."""


class GatherCompletedEvent(_GatherEventBase):
    """Fired when the gather future itself resolves successfully."""

    event_type: Literal["asyncio.gather.completed"] = "asyncio.gather.completed"
    completed_count: int = 0
    cancelled_children: int = 0
    failed_children: int = 0
    duration_seconds: float | None = None


class GatherCancelledEvent(_GatherEventBase):
    """Fired when the gather future is cancelled."""

    event_type: Literal["asyncio.gather.cancelled"] = "asyncio.gather.cancelled"
    completed_count: int = 0
    duration_seconds: float | None = None


class GatherFailedEvent(_GatherEventBase):
    """Fired when the gather future resolves with an exception (i.e. a
    child raised and ``return_exceptions`` was ``False``)."""

    event_type: Literal["asyncio.gather.failed"] = "asyncio.gather.failed"
    completed_count: int = 0
    duration_seconds: float | None = None
    exception_type: str | None = None
    """Class name of the propagated exception (e.g. ``"ValueError"``).
    Never carries the message or traceback — replay safety + payload
    redaction policy match the rest of the event families."""


#: Canonical ordered tuple of every gather event type. Mirrored in
#: :data:`asyncviz.runtime.events.models.enums.EventType`.
GATHER_EVENT_TYPES: tuple[str, ...] = (
    "asyncio.gather.created",
    "asyncio.gather.child.attached",
    "asyncio.gather.wait.started",
    "asyncio.gather.child.completed",
    "asyncio.gather.completed",
    "asyncio.gather.cancelled",
    "asyncio.gather.failed",
)
