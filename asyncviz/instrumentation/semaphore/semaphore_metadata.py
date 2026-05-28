"""Typed metadata records for instrumented ``asyncio.Semaphore``
instances.

Kept separate from the registry so we can build the dataclasses
without importing ``weakref``. The dashboard's diagnostics endpoint
hands these dicts to the wire layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

#: Single-source-of-truth classification for an instrumented semaphore.
#: ``subclass`` covers user subclasses of stdlib leaves. ``unknown``
#: is the defensive fallback for objects we can't classify (e.g.
#: future stdlib changes that introduce new leaves).
SemaphoreKind = Literal["Semaphore", "BoundedSemaphore", "subclass", "unknown"]


@dataclass(frozen=True, slots=True)
class SemaphoreIdentity:
    """Stable identity record for one instrumented semaphore."""

    semaphore_id: str
    """Monotonic ``s-N`` id allocated by the registry."""

    object_id: int
    """``id(semaphore)`` at registration time — only meaningful as long
    as the weakref keeps the object alive."""

    semaphore_kind: SemaphoreKind
    initial_value: int
    bound_value: int | None
    """Set for ``BoundedSemaphore`` instances; ``None`` for plain
    ``Semaphore``. The upper bound is recorded so the diagnostics
    layer can render the semaphore as a "permits in use" gauge."""

    created_at_ns: int
    creator_task_id: str | None
    name: str | None = None


@dataclass(frozen=True, slots=True)
class SemaphoreSnapshot:
    """Frozen view of a semaphore's current state.

    Carried inline on every emitted event so the consumer (renderer,
    replay reducer, diagnostics endpoint) can act on the data without
    keeping a registry handle.
    """

    semaphore_id: str
    current_value: int
    """``_value`` on the underlying semaphore — the number of permits
    available right now."""

    waiter_count: int
    """Length of the internal ``_waiters`` deque — tasks parked inside
    ``acquire``. ``waiter_count > 0`` always implies ``current_value
    == 0``."""

    initial_value: int
    bound_value: int | None
