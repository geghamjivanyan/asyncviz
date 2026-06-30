"""Runtime event models for ``asyncio.Semaphore`` instrumentation.

Each event is a typed Pydantic ``RuntimeEvent`` subclass; the
serializer registers them via :data:`EVENT_REGISTRY` so the wire
shape stays stable and the replay layer can reconstruct them
losslessly.

Schema notes:

* Every event carries the semaphore's identity (``semaphore_id``,
  ``semaphore_kind``, ``initial_value``, ``bound_value``) so a
  consumer can resolve the semaphore without keeping the registry
  in scope.
* ``snapshot`` carries the semaphore's current permit + waiter count
  so contention diagnostics don't need a sidecar lookup.
* ``task_id`` (when present) is the runtime-task-id of the actor
  performing the operation. ``None`` when the call originated outside
  any task (e.g. raw event loop work).
* Payloads are intentionally small — they never reference acquired
  permits or coroutine objects; everything required for replay is
  derivable from the typed fields.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from asyncviz.runtime.events.models.base import RuntimeEvent


class _SemaphoreEventBase(RuntimeEvent):
    """Shared envelope fields for every semaphore event."""

    semaphore_id: str
    semaphore_kind: str
    """``Semaphore`` / ``BoundedSemaphore`` / ``subclass`` / ``unknown``."""

    initial_value: int = 0
    bound_value: int | None = None
    task_id: str | None = None
    """Runtime-task-id of the actor performing the operation."""

    snapshot: dict[str, Any] = Field(default_factory=dict)
    """See :class:`asyncviz.instrumentation.semaphore.SemaphoreSnapshot`."""

    metadata: dict[str, Any] = Field(default_factory=dict)


class SemaphoreCreatedEvent(_SemaphoreEventBase):
    event_type: Literal["asyncio.semaphore.created"] = "asyncio.semaphore.created"
    creator_task_id: str | None = None
    name: str | None = None


class SemaphoreAcquireStartedEvent(_SemaphoreEventBase):
    """Emitted at the start of an ``acquire()`` call.

    Pairs with a subsequent :class:`SemaphoreAcquiredEvent` (success),
    :class:`SemaphoreWaitCancelledEvent` (cancellation), or — when the
    permit is granted without parking — only the acquired event fires
    immediately, and a started event is still emitted for symmetry."""

    event_type: Literal["asyncio.semaphore.acquire.started"] = "asyncio.semaphore.acquire.started"
    will_block: bool = False
    """``True`` when the caller had to park inside ``_waiters``; ``False``
    when the permit was granted synchronously."""


class SemaphoreAcquiredEvent(_SemaphoreEventBase):
    event_type: Literal["asyncio.semaphore.acquired"] = "asyncio.semaphore.acquired"
    blocked: bool = False
    """Mirrors ``will_block`` on the started event."""
    wait_seconds: float | None = None


class SemaphoreReleasedEvent(_SemaphoreEventBase):
    event_type: Literal["asyncio.semaphore.released"] = "asyncio.semaphore.released"


class SemaphoreContentionDetectedEvent(_SemaphoreEventBase):
    """Leading-edge event for blocked-waiter transitions.

    Fires when ``waiter_count`` rises from below the configured
    contention threshold to at-or-above it. The pair "contention
    cleared" is intentionally not modelled yet — keeping the schema
    forward-compatible for a future addition."""

    event_type: Literal["asyncio.semaphore.contention.detected"] = (
        "asyncio.semaphore.contention.detected"
    )
    waiter_count: int = 0
    current_value: int = 0


class SemaphoreWaitCancelledEvent(_SemaphoreEventBase):
    event_type: Literal["asyncio.semaphore.wait.cancelled"] = "asyncio.semaphore.wait.cancelled"
    wait_seconds: float | None = None


#: Canonical ordered tuple of every semaphore event type. Mirrored in
#: :data:`asyncviz.runtime.events.models.enums.EventType`.
SEMAPHORE_EVENT_TYPES: tuple[str, ...] = (
    "asyncio.semaphore.created",
    "asyncio.semaphore.acquire.started",
    "asyncio.semaphore.acquired",
    "asyncio.semaphore.released",
    "asyncio.semaphore.contention.detected",
    "asyncio.semaphore.wait.cancelled",
)
