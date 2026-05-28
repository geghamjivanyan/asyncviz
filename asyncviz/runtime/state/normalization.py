"""Event → normalized intent translation.

Reducers consume the typed event classes from
:mod:`asyncviz.runtime.events.models`, but the *state store* wants a
slightly broader view: it cares about which event types should mutate state
at all, and what sequence number applies. This module lives in between so
those concerns stay out of the reducer functions themselves.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models import (
    TaskCancelledEvent,
    TaskCompletedEvent,
    TaskCreatedEvent,
    TaskFailedEvent,
    TaskResumedEvent,
    TaskStartedEvent,
    TaskWaitingEvent,
)

#: Event classes that mutate task state. Anything outside this set is a
#: no-op for the store (counted as ``events_unknown_type``).
TASK_EVENT_TYPES: tuple[type[RuntimeEvent], ...] = (
    TaskCreatedEvent,
    TaskStartedEvent,
    TaskWaitingEvent,
    TaskResumedEvent,
    TaskCompletedEvent,
    TaskCancelledEvent,
    TaskFailedEvent,
)


@dataclass(frozen=True, slots=True)
class NormalizedEvent:
    """Decision record produced by :func:`normalize_event`.

    Carries the original event plus the metadata the store needs to dispatch:
    is it a task event? what's its ordering sequence? is the event id known?
    """

    event: RuntimeEvent
    is_task_event: bool
    sequence: int | None
    event_id: str
    event_type: str


def normalize_event(event: RuntimeEvent, *, sequence: int | None) -> NormalizedEvent:
    """Wrap ``event`` in the metadata the store needs to apply it.

    ``sequence`` is whatever the caller knows — typically the queue's
    :class:`QueuedEvent.sequence` for the live path or the recorded
    sequence on a replay item.
    """
    return NormalizedEvent(
        event=event,
        is_task_event=isinstance(event, TASK_EVENT_TYPES),
        sequence=sequence,
        event_id=str(event.event_id),
        event_type=event.event_type,
    )
