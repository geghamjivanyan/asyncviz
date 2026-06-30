"""Bounded LRU caches for reducer-derived state.

Each domain reducer (tasks, queues, semaphores, etc.) can register
its derived caches here and the optimizer enforces a soft cap on
entry count. When the cap fills, the LRU entry is evicted.

Distinct from the reducer registry itself — that's about *which*
reducers run; this is about *what* state they're allowed to keep
around between invocations.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from asyncviz.runtime.memory.memory_observability import get_memory_metrics
from asyncviz.runtime.memory.memory_tracing import record_memory_trace


class BoundedReducerCache[K, V]:
    """LRU cache for reducer-derived state."""

    __slots__ = ("_buf", "_capacity", "_lock", "_name")

    def __init__(self, name: str, capacity: int = 512) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._name = name
        self._capacity = capacity
        self._buf: OrderedDict[K, V] = OrderedDict()
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def capacity(self) -> int:
        return self._capacity

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)

    def get(self, key: K) -> V | None:
        with self._lock:
            value = self._buf.get(key)
            if value is None:
                return None
            self._buf.move_to_end(key)
            return value

    def put(self, key: K, value: V) -> None:
        with self._lock:
            if key in self._buf:
                self._buf.move_to_end(key)
                self._buf[key] = value
                return
            self._buf[key] = value
            while len(self._buf) > self._capacity:
                self._buf.popitem(last=False)
                get_memory_metrics().record_reducer_eviction()
                record_memory_trace(
                    "reducer-evicted",
                    f"cache={self._name}",
                )

    def discard(self, key: K) -> None:
        with self._lock:
            self._buf.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()

    def items(self) -> tuple[tuple[K, V], ...]:
        with self._lock:
            return tuple(self._buf.items())


def get_or_compute[K, V](
    cache: BoundedReducerCache[K, V],
    key: K,
    factory: Callable[[], V],
) -> V:
    """Convenience helper — return the cached value or compute +
    cache + return a fresh one."""
    value = cache.get(key)
    if value is not None:
        return value
    fresh = factory()
    cache.put(key, fresh)
    return fresh


# ── projection-reuse helpers ──────────────────────────────────────


class ProjectionReusePool[K]:
    """Tracks the last-projected dict per key so consumers can
    avoid rebuilding identical projections.

    Returns the *same* dict instance when the inputs are
    structurally equal — significant memory + GC savings when the
    projection set is stable but reads are frequent (timeline
    overlay refreshes, dashboard polling)."""

    __slots__ = ("_lock", "_table")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._table: dict[K, dict[str, Any]] = {}

    def reuse_or_store(self, key: K, projection: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            previous = self._table.get(key)
            if previous is not None and previous == projection:
                return previous
            self._table[key] = projection
            return projection

    def invalidate(self, key: K) -> None:
        with self._lock:
            self._table.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._table.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._table)
