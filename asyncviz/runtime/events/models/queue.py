"""Runtime event models for ``asyncio.Queue`` instrumentation.

Each event is a typed Pydantic ``RuntimeEvent`` subclass; the
serializer registers them via ``EVENT_REGISTRY`` so the wire shape
stays stable + the replay layer can reconstruct them losslessly.

Schema notes:

* Every event carries the queue's identity (``queue_id``,
  ``queue_kind``, ``maxsize``) so a consumer can resolve the queue
  without keeping the registry in scope.
* ``snapshot`` carries the queue's *current* size + blocked-task
  counts so backpressure diagnostics don't need a sidecar lookup.
* ``task_id`` (when present) is the runtime-task-id of the task
  performing the operation, populated from the same context the
  task patcher uses.
* Payloads are intentionally tiny — they never reference the queued
  *value*. Capturing user payloads on every event would dominate the
  hot path + leak object references.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from asyncviz.runtime.events.models.base import RuntimeEvent


class _QueueEventBase(RuntimeEvent):
    """Shared fields for every queue event."""

    queue_id: str
    queue_kind: str
    """``Queue`` / ``PriorityQueue`` / ``LifoQueue`` / ``subclass`` /
    ``unknown``."""
    maxsize: int = 0
    task_id: str | None = None
    """Runtime-task-id of the actor performing the operation
    (``None`` when called from a non-task context)."""
    snapshot: dict[str, Any] = Field(default_factory=dict)
    """Frozen view of the queue at the moment the event fired.
    See :class:`asyncviz.instrumentation.queue.QueueSnapshot`."""
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueueCreatedEvent(_QueueEventBase):
    event_type: Literal["asyncio.queue.created"] = "asyncio.queue.created"
    creator_task_id: str | None = None
    name: str | None = None


class QueuePutEvent(_QueueEventBase):
    event_type: Literal["asyncio.queue.put"] = "asyncio.queue.put"
    nowait: bool = False
    """``True`` when the caller used ``put_nowait``."""
    blocked: bool = False
    """``True`` when the caller had to wait (queue was full + blocked)."""
    wait_seconds: float | None = None


class QueueGetEvent(_QueueEventBase):
    event_type: Literal["asyncio.queue.get"] = "asyncio.queue.get"
    nowait: bool = False
    blocked: bool = False
    wait_seconds: float | None = None


class QueueFullWaitEvent(_QueueEventBase):
    """Emitted when a producer is about to await on a full queue.

    Pairs with a subsequent :class:`QueuePutEvent` carrying
    ``blocked=True`` + the resolved ``wait_seconds``.
    """

    event_type: Literal["asyncio.queue.full_wait"] = "asyncio.queue.full_wait"


class QueueEmptyWaitEvent(_QueueEventBase):
    """Emitted when a consumer is about to await on an empty queue."""

    event_type: Literal["asyncio.queue.empty_wait"] = "asyncio.queue.empty_wait"


class QueueTaskDoneEvent(_QueueEventBase):
    event_type: Literal["asyncio.queue.task_done"] = "asyncio.queue.task_done"


class QueueCancelledEvent(_QueueEventBase):
    """Emitted when a put/get await is cancelled."""

    event_type: Literal["asyncio.queue.cancelled"] = "asyncio.queue.cancelled"
    operation: Literal["put", "get"] = "get"
    wait_seconds: float | None = None


QUEUE_EVENT_TYPES: tuple[str, ...] = (
    "asyncio.queue.created",
    "asyncio.queue.put",
    "asyncio.queue.get",
    "asyncio.queue.full_wait",
    "asyncio.queue.empty_wait",
    "asyncio.queue.task_done",
    "asyncio.queue.cancelled",
)
