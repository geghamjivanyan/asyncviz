"""Typed metadata records for instrumented ``asyncio.Queue`` instances.

These dataclasses are the on-wire shape used by the event payloads
+ the dashboard inspector. Keeping them frozen + slot-backed keeps
the per-event overhead low.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

QueueKind = Literal["Queue", "PriorityQueue", "LifoQueue", "subclass", "unknown"]


@dataclass(frozen=True, slots=True)
class QueueIdentity:
    """Stable identity for one queue instance.

    The ``queue_id`` is a monotonic process-wide counter; ``object_id``
    is the underlying ``id()`` of the Python object — useful only
    while the queue is alive (Python reuses ids after garbage
    collection), but cheap to compute and helpful when correlating
    with a live debugger.
    """

    queue_id: str
    object_id: int
    queue_kind: QueueKind
    maxsize: int
    created_at_ns: int
    creator_task_id: str | None
    name: str | None = None


@dataclass(frozen=True, slots=True)
class QueueSnapshot:
    """Per-queue snapshot recorded with each event.

    Carries the queue's *current* size + blocked-task counts so a
    consumer (replay viewer, diagnostics endpoint) can compute
    backpressure without re-reading the live queue.
    """

    queue_id: str
    size: int
    maxsize: int
    blocked_putters: int
    blocked_getters: int
    unfinished_tasks: int
