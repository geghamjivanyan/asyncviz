"""Reconstructed-state LRU cache.

Scrubbing rapidly back and forth across the same neighborhood is
the *primary* workload the seek coordinator optimizes for — the
cache makes repeat seeks O(0) by holding recently-reconstructed
:class:`VirtualRuntimeState` snapshots keyed by sequence.

Bounded by entry count (not bytes), since virtual state size is
domain-dependent and varies between recordings. ``cache_capacity``
defaults to 16 — enough to make a 32-step scrub burst land in
cache 50% of the time without taking measurable memory.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass

from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState


@dataclass(frozen=True, slots=True)
class SeekCacheEntry:
    """One cached reconstruction."""

    sequence: int
    monotonic_ns: int
    state: VirtualRuntimeState


@dataclass(slots=True)
class SeekCacheStats:
    capacity: int
    size: int
    hits: int
    misses: int
    evictions: int


class SeekCache:
    """Bounded-LRU keyed by reconstruction-target sequence."""

    __slots__ = (
        "_capacity",
        "_entries",
        "_evictions",
        "_hits",
        "_lock",
        "_misses",
    )

    def __init__(self, capacity: int = 16) -> None:
        if capacity < 0:
            raise ValueError("capacity must be >= 0")
        self._capacity = capacity
        self._entries: OrderedDict[int, SeekCacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._entries)

    def get(self, sequence: int) -> SeekCacheEntry | None:
        if self._capacity == 0:
            return None
        with self._lock:
            entry = self._entries.get(sequence)
            if entry is None:
                self._misses += 1
                return None
            self._entries.move_to_end(sequence)
            self._hits += 1
            return entry

    def put(self, entry: SeekCacheEntry) -> None:
        if self._capacity == 0:
            return
        with self._lock:
            if entry.sequence in self._entries:
                self._entries.move_to_end(entry.sequence)
                self._entries[entry.sequence] = entry
                return
            self._entries[entry.sequence] = entry
            while len(self._entries) > self._capacity:
                self._entries.popitem(last=False)
                self._evictions += 1

    def invalidate(self, sequence: int | None = None) -> None:
        with self._lock:
            if sequence is None:
                self._entries.clear()
                return
            self._entries.pop(sequence, None)

    def stats(self) -> SeekCacheStats:
        with self._lock:
            return SeekCacheStats(
                capacity=self._capacity,
                size=len(self._entries),
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
            )
