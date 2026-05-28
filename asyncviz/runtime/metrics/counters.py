"""Thread-safe counter primitives used across the aggregator."""

from __future__ import annotations

import threading
from collections import defaultdict


class CounterSet:
    """Atomic ``str -> int`` counter map.

    Each named counter is independently incrementable; reads return an
    atomic point-in-time snapshot via :meth:`snapshot`. Designed so the
    aggregator can group counts by an arbitrary key (coroutine_name,
    cancellation_origin, etc.) without one defaultdict per dimension.
    """

    __slots__ = ("_counts", "_lock")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[str, int] = defaultdict(int)

    def inc(self, key: str, *, delta: int = 1) -> int:
        with self._lock:
            self._counts[key] += delta
            return self._counts[key]

    def add(self, mapping: dict[str, int]) -> None:
        with self._lock:
            for k, v in mapping.items():
                self._counts[k] += v

    def get(self, key: str) -> int:
        with self._lock:
            return self._counts.get(key, 0)

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()

    def total(self) -> int:
        with self._lock:
            return sum(self._counts.values())

    def keys(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._counts.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._counts)

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counts)
