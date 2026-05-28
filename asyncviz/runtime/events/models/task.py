from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from asyncviz.runtime.events.models.base import RuntimeEvent


class _TaskEventBase(RuntimeEvent):
    """Shared task-event fields. Not used directly; subclass instead."""

    task_id: str
    parent_task_id: str | None = None
    coroutine_name: str | None = None
    task_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class _TerminalTaskEventBase(_TaskEventBase):
    """Fields shared by every terminal task event.

    Carrying ``created_at``, ``completed_at``, and ``duration_seconds`` on
    every terminal frame makes them self-contained for replay — consumers
    never need to cross-reference the corresponding ``TaskCreatedEvent``.

    Timing semantics:
      * ``created_at``       — wall-clock when the task was first observed.
      * ``completed_at``     — wall-clock when this terminal event fires.
      * ``duration_seconds`` — computed from :func:`time.monotonic`, so it's
        drift-safe and **never negative** (clamped to 0 on edge cases).
    """

    created_at: float | None = None
    completed_at: float | None = None
    duration_seconds: float | None = None


class TaskCreatedEvent(_TaskEventBase):
    event_type: Literal["asyncio.task.created"] = "asyncio.task.created"


class TaskStartedEvent(_TaskEventBase):
    event_type: Literal["asyncio.task.started"] = "asyncio.task.started"


class TaskWaitingEvent(_TaskEventBase):
    event_type: Literal["asyncio.task.waiting"] = "asyncio.task.waiting"
    reason: str | None = None


class TaskResumedEvent(_TaskEventBase):
    event_type: Literal["asyncio.task.resumed"] = "asyncio.task.resumed"


class TaskCompletedEvent(_TerminalTaskEventBase):
    event_type: Literal["asyncio.task.completed"] = "asyncio.task.completed"


class TaskCancelledEvent(_TerminalTaskEventBase):
    event_type: Literal["asyncio.task.cancelled"] = "asyncio.task.cancelled"
    #: Best-effort hint at what caused the cancellation. Reserved values:
    #: ``"explicit"`` (user-called ``task.cancel()``), ``"timeout"``
    #: (raised by ``asyncio.wait_for`` / ``asyncio.timeout``), ``"parent"``
    #: (parent task propagated cancellation), ``"shutdown"`` (runtime
    #: teardown). Instrumentation leaves this ``None`` for now —
    #: cause-tracking is wired in a follow-up task.
    cancellation_origin: str | None = None


class TaskFailedEvent(_TerminalTaskEventBase):
    event_type: Literal["asyncio.task.failed"] = "asyncio.task.failed"
    exception_type: str | None = None
    exception_message: str | None = None
