"""Process-wide string interner for event-related keys.

The same task names, event types, runtime ids, and topology labels
show up millions of times across a long-running runtime. Interning
collapses each one to a single canonical Python ``str`` instance,
so:

1. Equality checks become pointer comparisons (CPython optimizes
   ``a is b`` for interned strings).
2. Dictionary keys stop allocating per-event.
3. Memory footprint scales with *unique* strings, not *uses*.

The interner is bounded — once the capacity fills, new strings
bypass interning rather than evicting old entries. Eviction would
break the canonical-identity guarantee callers depend on.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InternerStats:
    capacity: int
    size: int
    hits: int
    misses: int
    bypassed: int
    """Lookups that fell back to the raw string because the table
    was full."""


class StringInterner:
    """Bounded canonical-string interner."""

    __slots__ = ("_bypassed", "_capacity", "_hits", "_lock", "_misses", "_table")

    def __init__(self, capacity: int = 4096) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._table: dict[str, str] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._bypassed = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    def __len__(self) -> int:
        with self._lock:
            return len(self._table)

    def intern(self, value: str) -> str:
        """Return the canonical instance for ``value``."""
        if not isinstance(value, str):
            raise TypeError(f"intern() expects str, got {type(value).__name__}")
        with self._lock:
            existing = self._table.get(value)
            if existing is not None:
                self._hits += 1
                return existing
            if len(self._table) >= self._capacity:
                # Don't evict — return the raw string. Eviction would
                # silently break ``a is b`` invariants downstream.
                self._bypassed += 1
                return value
            # Use Python's built-in intern() so the underlying string
            # storage is shared with the rest of the interpreter when
            # possible.
            canonical = sys.intern(value)
            self._table[canonical] = canonical
            self._misses += 1
            return canonical

    def intern_many(self, values: Iterable[str]) -> tuple[str, ...]:
        return tuple(self.intern(v) for v in values)

    def contains(self, value: str) -> bool:
        with self._lock:
            return value in self._table

    def stats(self) -> InternerStats:
        with self._lock:
            return InternerStats(
                capacity=self._capacity,
                size=len(self._table),
                hits=self._hits,
                misses=self._misses,
                bypassed=self._bypassed,
            )

    def clear(self) -> None:
        with self._lock:
            self._table.clear()
            self._hits = 0
            self._misses = 0
            self._bypassed = 0


_GLOBAL_INTERNER: StringInterner | None = None
_GLOBAL_LOCK = threading.Lock()


def get_global_interner() -> StringInterner:
    global _GLOBAL_INTERNER
    if _GLOBAL_INTERNER is None:
        with _GLOBAL_LOCK:
            if _GLOBAL_INTERNER is None:
                _GLOBAL_INTERNER = StringInterner()
    return _GLOBAL_INTERNER


def reset_global_interner() -> None:
    if _GLOBAL_INTERNER is not None:
        _GLOBAL_INTERNER.clear()
