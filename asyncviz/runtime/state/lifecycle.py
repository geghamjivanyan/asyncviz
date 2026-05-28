"""Lifecycle helpers — bind the store to the event bus / queue and tear it down."""

from __future__ import annotations

from typing import TYPE_CHECKING

from asyncviz.runtime.events import EventBus, RuntimeEvent, Subscription

if TYPE_CHECKING:
    from asyncviz.runtime.state.store import RuntimeStateStore


def bind_store_to_event_bus(
    store: RuntimeStateStore,
    bus: EventBus,
) -> Subscription:
    """Subscribe ``store.apply`` to every event on the bus.

    Returns the subscription handle so callers (typically the dashboard
    lifespan) can ``bus.unsubscribe(...)`` on teardown.

    The store is wildcard — it filters non-task events itself rather than
    asking the bus to do it, so future event types automatically flow
    through state observability counters even when they don't mutate state.
    """

    def _forward(event: RuntimeEvent) -> None:
        store.apply(event)

    return bus.subscribe(_forward)
