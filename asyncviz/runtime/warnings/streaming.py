"""Subscription / delta types for the warning manager."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from asyncviz.runtime.warnings.lifecycle import WarningLifecycle


class WarningChange(StrEnum):
    """What just happened to a warning."""

    ACTIVATED = "activated"
    UPDATED = "updated"
    DEDUPLICATED = "deduplicated"
    RESOLVED = "resolved"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class WarningDelta:
    """One incremental update emitted by the manager."""

    warning: WarningLifecycle
    change: WarningChange
    sequence: int | None
    last_sequence: int


WarningListener = Callable[[WarningDelta], None]


@dataclass(slots=True)
class WarningSubscription:
    """Handle returned by :meth:`WarningSubscriptionRegistry.add`."""

    id: int
    listener: WarningListener

    def __hash__(self) -> int:
        return self.id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, WarningSubscription) and other.id == self.id


class WarningSubscriptionRegistry:
    """Synchronous fan-out for warning deltas."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_id = 0
        self._listeners: dict[int, WarningSubscription] = {}

    def add(self, listener: WarningListener) -> WarningSubscription:
        with self._lock:
            self._next_id += 1
            sub = WarningSubscription(id=self._next_id, listener=listener)
            self._listeners[sub.id] = sub
        return sub

    def remove(self, subscription_or_id: WarningSubscription | int) -> bool:
        sub_id = (
            subscription_or_id.id
            if isinstance(subscription_or_id, WarningSubscription)
            else subscription_or_id
        )
        with self._lock:
            return self._listeners.pop(sub_id, None) is not None

    def listeners(self) -> list[WarningSubscription]:
        with self._lock:
            return list(self._listeners.values())

    def count(self) -> int:
        with self._lock:
            return len(self._listeners)

    def clear(self) -> None:
        with self._lock:
            self._listeners.clear()
