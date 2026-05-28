from __future__ import annotations

import threading
from collections import deque
from collections.abc import Iterator

from asyncviz.runtime.queue.buffering import QueuedEvent
from asyncviz.runtime.queue.exceptions import RetentionConfigError


class RetentionBuffer:
    """Bounded ring buffer of recently dispatched events for replay.

    Holds the last ``capacity`` :class:`QueuedEvent`\\ s in publish order so a
    reconnecting websocket client can request "everything since sequence N"
    and receive an exact replay — *iff* the requested sequence is still
    within the retention window.

    Thread-safe. The retention buffer is read by the websocket bridge (from
    the dashboard loop) and written by the queue's dispatcher (also on the
    dashboard loop), so contention is theoretically nil; the lock exists for
    correctness when test code reads the buffer from arbitrary threads.

    Memory bound: ``capacity * sizeof(QueuedEvent)`` — events are not copied,
    only referenced, so the actual cost is one ``QueuedEvent`` slot plus the
    underlying ``RuntimeEvent`` (which is shared with subscribers).
    """

    def __init__(self, capacity: int) -> None:
        if capacity < 0:
            raise RetentionConfigError(f"retention capacity must be ≥ 0 (got {capacity})")
        self._capacity = capacity
        self._lock = threading.Lock()
        self._items: deque[QueuedEvent] = deque(maxlen=capacity) if capacity > 0 else deque()
        self._enabled = capacity > 0
        # Bookkeeping for replay-miss accounting.
        self._oldest_evicted_sequence: int | None = None

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def enabled(self) -> bool:
        return self._enabled

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def append(self, item: QueuedEvent) -> None:
        """Record a freshly-dispatched event. Evicts the oldest when full."""
        if not self._enabled:
            return
        with self._lock:
            if len(self._items) == self._capacity and self._items:
                # The head is about to be evicted by ``deque(maxlen)``; remember
                # its sequence so we can answer "you missed events older than X"
                # for replay-miss observability.
                self._oldest_evicted_sequence = self._items[0].sequence
            self._items.append(item)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._oldest_evicted_sequence = None

    def snapshot(self) -> tuple[QueuedEvent, ...]:
        """Immutable point-in-time view, ordered from oldest to newest."""
        with self._lock:
            return tuple(self._items)

    def __iter__(self) -> Iterator[QueuedEvent]:
        # Snapshot semantics: caller iterates a copy so retention can mutate.
        return iter(self.snapshot())

    @property
    def oldest_sequence(self) -> int | None:
        with self._lock:
            return self._items[0].sequence if self._items else None

    @property
    def newest_sequence(self) -> int | None:
        with self._lock:
            return self._items[-1].sequence if self._items else None

    def events_since(self, sequence: int) -> tuple[QueuedEvent, ...]:
        """Return retained events with ``sequence > given`` in publish order.

        Pass ``0`` to receive the entire retained window. The caller should
        cross-check the result's first sequence against ``sequence + 1`` to
        detect a replay miss (retention window has rolled past the request).
        """
        with self._lock:
            return tuple(item for item in self._items if item.sequence > sequence)

    def has_sequence(self, sequence: int) -> bool:
        """Whether ``sequence`` is still inside the retention window.

        Treats ``sequence == 0`` as always satisfiable (means "from the
        start of what we have"). Otherwise true iff retention currently
        holds an event with sequence ``> sequence - 1`` and the requested
        ``sequence`` is still ≤ newest.
        """
        if sequence <= 0:
            return True
        with self._lock:
            if not self._items:
                return False
            return self._items[0].sequence <= sequence + 1 <= self._items[-1].sequence + 1
