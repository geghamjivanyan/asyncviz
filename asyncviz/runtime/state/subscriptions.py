"""Subscription registry for state-store change notifications.

Distinct from :mod:`asyncviz.runtime.events.subscriber` — that subscribes
to *raw events*. Listeners here see :class:`StateChange` records, which
arrive *after* the reducer has run and carry both the triggering event and
the store's high-water sequence.

The dispatch loop is synchronous; failures are isolated per-listener so
one buggy subscriber can't drop notifications for the rest.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from asyncviz.runtime.events.event import RuntimeEvent

#: Listener signature. The callback is invoked synchronously from the
#: store's apply path; expensive work belongs in a queue downstream.
StateListener = Callable[["StateChange"], None]


@dataclass(frozen=True, slots=True)
class StateChange:
    """Notification dispatched to listeners after a successful apply."""

    event: RuntimeEvent
    sequence: int | None
    last_sequence: int
    decision: str  # ReconciliationDecision.value
    event_type: str
    event_id: str


@dataclass(slots=True)
class StateSubscription:
    """Handle returned by :meth:`StateSubscriptionRegistry.add`."""

    id: int
    listener: StateListener

    def __hash__(self) -> int:
        return self.id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, StateSubscription) and other.id == self.id


class StateSubscriptionRegistry:
    """Tiny thread-safe registry for state-change listeners.

    Intentionally simpler than the event-bus registry: there's no event-type
    filtering (state changes are always emitted as one stream) and no async
    dispatch (the store calls listeners synchronously).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_id = 0
        self._listeners: dict[int, StateSubscription] = {}

    def add(self, listener: StateListener) -> StateSubscription:
        with self._lock:
            self._next_id += 1
            sub = StateSubscription(id=self._next_id, listener=listener)
            self._listeners[sub.id] = sub
        return sub

    def remove(self, subscription_or_id: StateSubscription | int) -> bool:
        sub_id = (
            subscription_or_id.id
            if isinstance(subscription_or_id, StateSubscription)
            else subscription_or_id
        )
        with self._lock:
            return self._listeners.pop(sub_id, None) is not None

    def listeners(self) -> list[StateSubscription]:
        with self._lock:
            return list(self._listeners.values())

    def count(self) -> int:
        with self._lock:
            return len(self._listeners)

    def clear(self) -> None:
        with self._lock:
            self._listeners.clear()
