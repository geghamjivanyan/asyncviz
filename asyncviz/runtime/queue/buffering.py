from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.events.event import RuntimeEvent


@dataclass(frozen=True, slots=True)
class QueuedEvent:
    """An event plus the queue-allocated sequence number that orders it.

    The sequence is allocated by the queue (via the bound :class:`RuntimeClock`)
    at the moment of :meth:`InternalEventQueue.publish`. Once allocated it is
    immutable and identifies the event uniquely within the runtime's lifetime.

    This is the data type that flows on the internal channel and lives in the
    retention ring. Consumers (the dispatcher, the WS bridge replay path) see
    ``QueuedEvent``\\ s; downstream subscribers see just the underlying
    :class:`RuntimeEvent`.
    """

    sequence: int
    event: RuntimeEvent
