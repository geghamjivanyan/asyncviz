"""Bounded coordination queue.

Pause/resume/step requests land on a small deque. The deque has a
capacity; when it fills, we *drop the oldest* request rather than
block. Reason: most replay UIs spit out rapid pause/resume bursts
(user mashing a button); the *latest* intent reflects what the user
actually wants, so dropping the stale ones is the right policy.

Drops are counted (``backpressure_events``) and traced
(``backpressure``) so misuse shows up in diagnostics.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass


class CoordinationQueueOverflowError(RuntimeError):
    """Raised in strict mode when the queue would overflow."""


@dataclass(slots=True)
class CoordinationQueueStats:
    """Snapshot of the queue's bookkeeping."""

    capacity: int
    depth: int
    accepted: int
    dropped_oldest: int


class CoordinationQueue[T]:
    """Bounded drop-oldest queue used for pause/resume requests."""

    __slots__ = ("_accepted", "_buf", "_capacity", "_dropped", "_lock")

    def __init__(self, capacity: int = 64) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._buf: deque[T] = deque()
        self._lock = threading.Lock()
        self._accepted = 0
        self._dropped = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)

    def offer(self, item: T) -> T | None:
        """Accept ``item``. Returns the evicted item if the queue
        had to drop one to make room, ``None`` otherwise."""
        with self._lock:
            evicted: T | None = None
            if len(self._buf) >= self._capacity:
                evicted = self._buf.popleft()
                self._dropped += 1
            self._buf.append(item)
            self._accepted += 1
            return evicted

    def drain(self) -> list[T]:
        """Pop every queued item."""
        with self._lock:
            items = list(self._buf)
            self._buf.clear()
            return items

    def peek(self) -> T | None:
        with self._lock:
            return self._buf[0] if self._buf else None

    def stats(self) -> CoordinationQueueStats:
        with self._lock:
            return CoordinationQueueStats(
                capacity=self._capacity,
                depth=len(self._buf),
                accepted=self._accepted,
                dropped_oldest=self._dropped,
            )
