"""Subscription / delta types for the metrics aggregator.

Listeners receive a :class:`MetricsDelta` after every successful apply. The
delta is intentionally lightweight — it carries the incremental info
needed for live charts (which counter changed, by how much, sequence) so
consumers can update without recomputing the whole snapshot.

Full-snapshot consumers should call :meth:`RuntimeMetricsAggregator.snapshot`
on demand instead.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from asyncviz.runtime.events.event import RuntimeEvent

MetricsListener = Callable[["MetricsDelta"], None]


@dataclass(frozen=True, slots=True)
class MetricsDelta:
    """One incremental update emitted by the aggregator.

    ``changes`` is a sparse ``str -> int`` map (e.g. ``{"completed": +1,
    "active": -1}``). ``duration_added_seconds`` is non-zero on terminal
    events. ``coroutine_name`` lets per-coroutine consumers narrow their
    update without re-reading the snapshot.
    """

    event: RuntimeEvent
    sequence: int | None
    last_sequence: int
    changes: dict[str, int]
    duration_added_seconds: float | None
    coroutine_name: str | None
    terminal_state: str | None


@dataclass(slots=True)
class MetricsSubscription:
    """Handle returned by :meth:`MetricsSubscriptionRegistry.add`."""

    id: int
    listener: MetricsListener

    def __hash__(self) -> int:
        return self.id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, MetricsSubscription) and other.id == self.id


class MetricsSubscriptionRegistry:
    """Tiny synchronous fan-out for :class:`MetricsDelta` listeners."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_id = 0
        self._listeners: dict[int, MetricsSubscription] = {}

    def add(self, listener: MetricsListener) -> MetricsSubscription:
        with self._lock:
            self._next_id += 1
            sub = MetricsSubscription(id=self._next_id, listener=listener)
            self._listeners[sub.id] = sub
        return sub

    def remove(self, subscription_or_id: MetricsSubscription | int) -> bool:
        sub_id = (
            subscription_or_id.id
            if isinstance(subscription_or_id, MetricsSubscription)
            else subscription_or_id
        )
        with self._lock:
            return self._listeners.pop(sub_id, None) is not None

    def listeners(self) -> list[MetricsSubscription]:
        with self._lock:
            return list(self._listeners.values())

    def count(self) -> int:
        with self._lock:
            return len(self._listeners)

    def clear(self) -> None:
        with self._lock:
            self._listeners.clear()
