"""Backpressure model + bounded queue used between the event source
and the writer thread.

The model is intentionally simple — the recorder is on the *hot
path*, so we never block the runtime. When the queue is full we
either drop the newest event (default) or, for opt-in users that
care more about completeness than runtime overhead, drop the oldest.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from enum import StrEnum


class BackpressureMode(StrEnum):
    """How to react when the in-memory queue is full."""

    DROP_NEWEST = "drop_newest"
    """Drop the just-arriving event. Cheapest + the most defensive
    choice — recording never delays the runtime."""

    DROP_OLDEST = "drop_oldest"
    """Evict the oldest queued event to make room. Keeps the trailing
    window fresh at the cost of dropping older context."""


@dataclass(frozen=True, slots=True)
class BackpressureOutcome:
    """Result of one ``offer`` call. Helps the recorder report drops."""

    accepted: bool
    dropped_count: int
    dropped_was_oldest: bool


class BoundedRecordQueue:
    """Thread-safe bounded queue of recorder records.

    Records are opaque to the queue — typically a tuple of
    ``(frame_dict, serialized_bytes)``.
    """

    def __init__(self, capacity: int, mode: BackpressureMode) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be positive, got {capacity}")
        self._capacity = capacity
        self._mode = mode
        self._items: deque[object] = deque()
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._total_dropped = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def total_dropped(self) -> int:
        return self._total_dropped

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def offer(self, item: object) -> BackpressureOutcome:
        """Try to enqueue ``item``. Never blocks."""
        with self._not_empty:
            if len(self._items) < self._capacity:
                self._items.append(item)
                self._not_empty.notify()
                return BackpressureOutcome(accepted=True, dropped_count=0, dropped_was_oldest=False)
            if self._mode is BackpressureMode.DROP_NEWEST:
                self._total_dropped += 1
                return BackpressureOutcome(
                    accepted=False,
                    dropped_count=1,
                    dropped_was_oldest=False,
                )
            # DROP_OLDEST
            self._items.popleft()
            self._items.append(item)
            self._total_dropped += 1
            self._not_empty.notify()
            return BackpressureOutcome(
                accepted=True,
                dropped_count=1,
                dropped_was_oldest=True,
            )

    def drain(self, max_items: int) -> list[object]:
        """Pop up to ``max_items`` items; non-blocking."""
        with self._lock:
            out: list[object] = []
            limit = min(max_items, len(self._items))
            for _ in range(limit):
                out.append(self._items.popleft())
            return out

    def wait_for_item(self, timeout: float) -> bool:
        """Block up to ``timeout`` seconds until at least one item exists."""
        with self._not_empty:
            if self._items:
                return True
            return self._not_empty.wait(timeout=timeout) and bool(self._items)

    def wake(self) -> None:
        """Notify waiters even without an item — used during shutdown."""
        with self._not_empty:
            self._not_empty.notify_all()
