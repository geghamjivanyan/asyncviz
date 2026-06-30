"""Runtime event models for ``run_in_executor`` instrumentation.

Schema notes:

* ``executor.registered`` is a lifecycle event (one per distinct
  executor instance the engine has seen). ``executor.work.*`` events
  carry both the executor id and the work-item id so downstream
  consumers can render either dimension independently.
* Payloads carry counters + ids + class-name strings — never the
  callable, the arguments, or the result/exception value. Same
  redaction policy as the rest of the event families.
* ``worker_thread_name`` is captured at ``work.started`` time from
  ``threading.current_thread().name``; the engine's worker tracker
  carries it forward so ``work.completed`` / ``work.failed`` events
  can re-surface it without re-reading the thread.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from asyncviz.runtime.events.models.base import RuntimeEvent


class _ExecutorEventBase(RuntimeEvent):
    """Shared envelope fields for every executor event."""

    executor_id: str
    executor_kind: str
    """``Thread`` / ``Process`` / ``default`` / ``custom`` / ``unknown``."""

    snapshot: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutorRegisteredEvent(_ExecutorEventBase):
    event_type: Literal["asyncio.executor.registered"] = "asyncio.executor.registered"
    max_workers: int | None = None
    thread_name_prefix: str | None = None
    creator_task_id: str | None = None
    name: str | None = None


class _WorkEventBase(_ExecutorEventBase):
    work_item_id: str
    submitting_task_id: str | None = None
    callable_name: str | None = None


class ExecutorWorkSubmittedEvent(_WorkEventBase):
    event_type: Literal["asyncio.executor.work.submitted"] = "asyncio.executor.work.submitted"


class ExecutorWorkStartedEvent(_WorkEventBase):
    """Fired from inside the executor thread when the user function is
    about to run."""

    event_type: Literal["asyncio.executor.work.started"] = "asyncio.executor.work.started"
    worker_thread_name: str | None = None
    submission_latency_seconds: float | None = None
    """``started_at - submitted_at``; surfaces queue latency for a
    blocking-offload diagnostics view."""


class ExecutorWorkCompletedEvent(_WorkEventBase):
    event_type: Literal["asyncio.executor.work.completed"] = "asyncio.executor.work.completed"
    worker_thread_name: str | None = None
    duration_seconds: float | None = None
    """``finished_at - started_at`` measured in the executor thread."""


class ExecutorWorkFailedEvent(_WorkEventBase):
    event_type: Literal["asyncio.executor.work.failed"] = "asyncio.executor.work.failed"
    worker_thread_name: str | None = None
    duration_seconds: float | None = None
    exception_type: str | None = None


class ExecutorWorkCancelledEvent(_WorkEventBase):
    event_type: Literal["asyncio.executor.work.cancelled"] = "asyncio.executor.work.cancelled"
    duration_seconds: float | None = None


#: Canonical ordered tuple of every executor event type.
EXECUTOR_EVENT_TYPES: tuple[str, ...] = (
    "asyncio.executor.registered",
    "asyncio.executor.work.submitted",
    "asyncio.executor.work.started",
    "asyncio.executor.work.completed",
    "asyncio.executor.work.failed",
    "asyncio.executor.work.cancelled",
)
