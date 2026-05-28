from __future__ import annotations

import threading
from collections import defaultdict
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.exceptions import InvalidSubscriptionError

EventCallback = Callable[[RuntimeEvent], Awaitable[None] | None]


@dataclass(slots=True)
class Subscription:
    """Handle returned by :meth:`EventBus.subscribe`.

    Stable identity comes from ``id``, never the callback. Two subscriptions
    that share a callback are still distinct subscriptions — they each get
    their own slot in the registry and can be removed independently.
    """

    id: int
    callback: EventCallback
    event_types: frozenset[str] | None

    @property
    def is_wildcard(self) -> bool:
        return self.event_types is None

    def __hash__(self) -> int:
        return self.id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Subscription) and other.id == self.id


class SubscriptionRegistry:
    """Indexed subscription store with O(matching) dispatch lookup.

    Thread-safe: ``subscribe`` and ``unsubscribe`` may be called from any
    thread (instrumentation code commonly subscribes outside the bus's loop).
    Reads happen exclusively from the dispatcher's loop thread, but the lock
    is cheap and we acquire it on the read path too — premature lock-free
    optimization is the wrong fight at this scale.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_id = 0
        self._by_id: dict[int, Subscription] = {}
        self._by_type: dict[str, set[int]] = defaultdict(set)
        self._wildcards: set[int] = set()

    def add(
        self,
        callback: EventCallback,
        event_types: Iterable[str] | None = None,
    ) -> Subscription:
        if not callable(callback):
            raise InvalidSubscriptionError(f"callback must be callable, got {callback!r}")
        types_fs = frozenset(event_types) if event_types is not None else None
        if types_fs is not None and not all(isinstance(t, str) and t for t in types_fs):
            raise InvalidSubscriptionError("event_types must be non-empty strings")

        with self._lock:
            self._next_id += 1
            sub = Subscription(id=self._next_id, callback=callback, event_types=types_fs)
            self._by_id[sub.id] = sub
            if types_fs is None:
                self._wildcards.add(sub.id)
            else:
                for t in types_fs:
                    self._by_type[t].add(sub.id)
        return sub

    def remove(self, sub_id: int) -> bool:
        with self._lock:
            sub = self._by_id.pop(sub_id, None)
            if sub is None:
                return False
            if sub.event_types is None:
                self._wildcards.discard(sub.id)
            else:
                for t in sub.event_types:
                    bucket = self._by_type.get(t)
                    if bucket is not None:
                        bucket.discard(sub.id)
                        if not bucket:
                            self._by_type.pop(t, None)
        return True

    def matching(self, event_type: str) -> list[Subscription]:
        with self._lock:
            ids = self._wildcards | self._by_type.get(event_type, set())
            return [self._by_id[i] for i in ids if i in self._by_id]

    def count(self) -> int:
        with self._lock:
            return len(self._by_id)

    def clear(self) -> None:
        with self._lock:
            self._by_id.clear()
            self._by_type.clear()
            self._wildcards.clear()
