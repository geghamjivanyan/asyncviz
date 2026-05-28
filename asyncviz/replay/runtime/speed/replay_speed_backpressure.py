"""Bounded coordination queue for speed-change requests.

Drop-oldest because the *latest* speed reflects what the user
actually wants. Rapid speed-change bursts collapse into the last
two-or-three requests, which is what the UX needs (slow-motion to
realtime to fast-forward transitions land cleanly).
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass


@dataclass(slots=True)
class SpeedQueueStats:
    capacity: int
    depth: int
    accepted: int
    dropped_oldest: int


class SpeedQueue[T]:
    """Bounded drop-oldest queue keyed by insertion order."""

    __slots__ = (
        "_accepted",
        "_buf",
        "_capacity",
        "_dropped",
        "_lock",
    )

    def __init__(self, capacity: int = 16) -> None:
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
        """Accept ``item`` + return any evicted predecessor."""
        with self._lock:
            evicted: T | None = None
            if len(self._buf) >= self._capacity:
                evicted = self._buf.popleft()
                self._dropped += 1
            self._buf.append(item)
            self._accepted += 1
            return evicted

    def drain(self) -> list[T]:
        with self._lock:
            items = list(self._buf)
            self._buf.clear()
            return items

    def peek(self) -> T | None:
        with self._lock:
            return self._buf[0] if self._buf else None

    def stats(self) -> SpeedQueueStats:
        with self._lock:
            return SpeedQueueStats(
                capacity=self._capacity,
                depth=len(self._buf),
                accepted=self._accepted,
                dropped_oldest=self._dropped,
            )
