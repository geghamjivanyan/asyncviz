"""Bounded object pool for transient buffers.

Designed for short-lived scratch objects (JSON serialization
buffers, compact-frame dicts) where acquiring + releasing has lower
overhead than constructing a fresh instance.

Safety model:

* Acquire returns a :class:`PoolToken` carrying the object + a
  release callback.
* Release returns the object to the pool, optionally resetting it
  via a caller-supplied ``reset`` function.
* Double-release is detected and either raises (strict mode) or is
  silently swallowed (lenient mode). The default is strict.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass


class PoolExhaustedError(RuntimeError):
    """Raised when a pool with ``block`` policy can't acquire."""


class PoolReleaseError(RuntimeError):
    """Raised on double-release under strict pool safety."""


@dataclass(slots=True)
class PoolStats:
    capacity: int
    size: int
    """Items currently *in* the pool, waiting to be reused."""
    in_flight: int
    """Items currently checked out via acquire()."""
    acquires: int
    releases: int
    pool_hits: int
    """Acquires that found a reusable item."""
    pool_misses: int
    """Acquires that had to construct a new item (pool empty)."""
    double_releases: int


class ObjectPool[T]:
    """Bounded LIFO pool with optional reset hook."""

    __slots__ = (
        "_acquires",
        "_buf",
        "_capacity",
        "_double_releases",
        "_factory",
        "_in_flight_ids",
        "_lock",
        "_pool_hits",
        "_pool_misses",
        "_releases",
        "_reset",
        "_strict",
    )

    def __init__(
        self,
        factory: Callable[[], T],
        *,
        capacity: int = 256,
        reset: Callable[[T], None] | None = None,
        strict: bool = True,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._factory = factory
        self._reset = reset
        self._capacity = capacity
        self._strict = strict
        self._buf: deque[T] = deque()
        self._in_flight_ids: set[int] = set()
        self._lock = threading.Lock()
        self._acquires = 0
        self._releases = 0
        self._pool_hits = 0
        self._pool_misses = 0
        self._double_releases = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    def acquire(self) -> PoolToken[T]:
        with self._lock:
            self._acquires += 1
            if self._buf:
                obj = self._buf.pop()
                self._pool_hits += 1
            else:
                obj = self._factory()
                self._pool_misses += 1
            self._in_flight_ids.add(id(obj))
        return PoolToken(pool=self, obj=obj)

    def _release(self, obj: T) -> None:
        with self._lock:
            obj_id = id(obj)
            if obj_id not in self._in_flight_ids:
                self._double_releases += 1
                if self._strict:
                    raise PoolReleaseError(
                        "release() called on object not in flight "
                        "(double release or stranger object)",
                    )
                return
            self._in_flight_ids.discard(obj_id)
            self._releases += 1
            if self._reset is not None:
                # Reset under lock — keeps the reset semantics
                # consistent with the pool's internal invariants.
                self._reset(obj)
            if len(self._buf) < self._capacity:
                self._buf.append(obj)
            # Else: pool is full, drop the object. GC handles it.

    def stats(self) -> PoolStats:
        with self._lock:
            return PoolStats(
                capacity=self._capacity,
                size=len(self._buf),
                in_flight=len(self._in_flight_ids),
                acquires=self._acquires,
                releases=self._releases,
                pool_hits=self._pool_hits,
                pool_misses=self._pool_misses,
                double_releases=self._double_releases,
            )

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()
            self._in_flight_ids.clear()


@dataclass(slots=True)
class PoolToken[T]:
    """Handle returned by :meth:`ObjectPool.acquire`."""

    pool: ObjectPool[T]
    obj: T
    _released: bool = False

    def release(self) -> None:
        """Return the object to the pool. Idempotent under lenient
        mode; raises under strict mode if called twice."""
        if self._released:
            if self.pool._strict:
                raise PoolReleaseError("token already released")
            return
        self._released = True
        self.pool._release(self.obj)

    def __enter__(self) -> T:
        return self.obj

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self.release()
