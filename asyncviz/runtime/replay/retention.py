"""Bounded ring of :class:`ReplayFrame` plus sequence-index map."""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Iterator

from asyncviz.runtime.replay.frames import ReplayFrame

#: Default replay-frame cap. ~4096 frames * ~1KB ≈ 4 MB worst case.
DEFAULT_FRAME_LIMIT: int = 4096


class FrameRetention:
    """Append-only ring of :class:`ReplayFrame` with O(1) sequence lookup.

    Designed so the WebSocket bridge can answer "everything since
    sequence N" in O(retained) and so the dashboard can answer
    "what's at sequence 4096?" in O(1).

    Threadsafe. The append path takes a single lock; reads return tuple
    snapshots so the lock doesn't span user code.
    """

    def __init__(self, *, capacity: int = DEFAULT_FRAME_LIMIT) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._lock = threading.Lock()
        self._frames: deque[ReplayFrame] = deque(maxlen=capacity)
        self._index: dict[int, ReplayFrame] = {}
        self._evicted_count = 0
        self._oldest_evicted_sequence: int | None = None

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def evicted_count(self) -> int:
        with self._lock:
            return self._evicted_count

    @property
    def oldest_evicted_sequence(self) -> int | None:
        with self._lock:
            return self._oldest_evicted_sequence

    def __len__(self) -> int:
        with self._lock:
            return len(self._frames)

    def append(self, frame: ReplayFrame) -> ReplayFrame | None:
        """Append a frame. Returns the evicted frame, if any."""
        with self._lock:
            evicted: ReplayFrame | None = None
            if len(self._frames) == self._capacity and self._frames:
                evicted = self._frames[0]
                self._evicted_count += 1
                self._oldest_evicted_sequence = evicted.sequence
                self._index.pop(evicted.sequence, None)
            self._frames.append(frame)
            self._index[frame.sequence] = frame
            return evicted

    def clear(self) -> None:
        with self._lock:
            self._frames.clear()
            self._index.clear()
            self._evicted_count = 0
            self._oldest_evicted_sequence = None

    def get(self, sequence: int) -> ReplayFrame | None:
        with self._lock:
            return self._index.get(sequence)

    def oldest_sequence(self) -> int | None:
        with self._lock:
            return self._frames[0].sequence if self._frames else None

    def newest_sequence(self) -> int | None:
        with self._lock:
            return self._frames[-1].sequence if self._frames else None

    def snapshot(self) -> tuple[ReplayFrame, ...]:
        with self._lock:
            return tuple(self._frames)

    def since(self, sequence: int) -> tuple[ReplayFrame, ...]:
        """All frames with ``frame.sequence > sequence``, in publish order."""
        with self._lock:
            return tuple(f for f in self._frames if f.sequence > sequence)

    def range(self, start: int, end: int) -> tuple[ReplayFrame, ...]:
        """All frames with ``start <= sequence <= end`` (inclusive)."""
        with self._lock:
            return tuple(f for f in self._frames if start <= f.sequence <= end)

    def covers(self, sequence: int) -> bool:
        """Whether ``sequence`` is still inside the retention window.

        ``sequence == 0`` (no events seen yet) is always covered — the
        full retained window serves as the replay.
        """
        if sequence <= 0:
            return True
        with self._lock:
            if not self._frames:
                return False
            oldest = self._frames[0].sequence
            newest = self._frames[-1].sequence
            return oldest - 1 <= sequence <= newest

    def __iter__(self) -> Iterator[ReplayFrame]:
        # Snapshot semantics — caller iterates a copy.
        return iter(self.snapshot())
