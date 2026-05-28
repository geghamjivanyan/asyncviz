"""Subscription registry for replay-frame notifications."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from asyncviz.runtime.replay.frames import ReplayFrame

ReplayListener = Callable[[ReplayFrame], None]


@dataclass(slots=True)
class ReplaySubscription:
    """Handle returned by :meth:`ReplaySubscriptionRegistry.add`."""

    id: int
    listener: ReplayListener

    def __hash__(self) -> int:
        return self.id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ReplaySubscription) and other.id == self.id


class ReplaySubscriptionRegistry:
    """Synchronous fan-out for replay-frame listeners.

    Today only used internally; the websocket bridge sources frames via
    ``replay_since`` rather than per-frame events. The subscription API
    is reserved so a future persistence recorder can attach.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_id = 0
        self._listeners: dict[int, ReplaySubscription] = {}

    def add(self, listener: ReplayListener) -> ReplaySubscription:
        with self._lock:
            self._next_id += 1
            sub = ReplaySubscription(id=self._next_id, listener=listener)
            self._listeners[sub.id] = sub
        return sub

    def remove(self, subscription_or_id: ReplaySubscription | int) -> bool:
        sub_id = (
            subscription_or_id.id
            if isinstance(subscription_or_id, ReplaySubscription)
            else subscription_or_id
        )
        with self._lock:
            return self._listeners.pop(sub_id, None) is not None

    def listeners(self) -> list[ReplaySubscription]:
        with self._lock:
            return list(self._listeners.values())

    def count(self) -> int:
        with self._lock:
            return len(self._listeners)

    def clear(self) -> None:
        with self._lock:
            self._listeners.clear()
