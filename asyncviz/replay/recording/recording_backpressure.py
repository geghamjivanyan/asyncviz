"""Drop policy primitives for the recording writer's bounded queue.

The writer accepts ``EnqueueResult`` from the policy to decide
whether the incoming event was accepted, displaced an older one, or
got dropped outright.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
from threading import Condition, Lock
from typing import Literal

PolicyAction = Literal["accepted", "dropped-newest", "dropped-oldest", "blocked"]


@dataclass(frozen=True, slots=True)
class EnqueueResult[T]:
    action: PolicyAction
    evicted: T | None = None


class BoundedRingBuffer[T]:
    """Thread-safe bounded buffer used by the writer worker.

    Drains are batched — :meth:`drain_batch` pops up to ``max_items``
    in one acquisition so the worker can do bulk writes.
    """

    __slots__ = ("_buf", "_capacity", "_cond", "_drop_policy", "_lock")

    def __init__(
        self,
        capacity: int,
        *,
        drop_policy: Literal["drop-newest", "drop-oldest", "block"] = "drop-newest",
    ) -> None:
        if capacity < 1:
            raise ValueError(f"capacity must be >= 1 (got {capacity})")
        self._capacity = capacity
        self._drop_policy = drop_policy
        self._lock = Lock()
        self._cond = Condition(self._lock)
        self._buf: deque[T] = deque()

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def drop_policy(self) -> str:
        return self._drop_policy

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)

    def offer(self, item: T) -> EnqueueResult[T]:
        """Try to add ``item``. Returns the policy outcome."""
        with self._cond:
            if len(self._buf) < self._capacity:
                self._buf.append(item)
                self._cond.notify()
                return EnqueueResult("accepted")
            if self._drop_policy == "drop-newest":
                return EnqueueResult("dropped-newest", evicted=item)
            if self._drop_policy == "drop-oldest":
                evicted = self._buf.popleft()
                self._buf.append(item)
                self._cond.notify()
                return EnqueueResult("dropped-oldest", evicted=evicted)
            # block
            while len(self._buf) >= self._capacity:
                self._cond.wait()
            self._buf.append(item)
            self._cond.notify()
            return EnqueueResult("blocked")

    def drain_batch(self, max_items: int, timeout: float | None = None) -> list[T]:
        """Block until at least one item is available or ``timeout``
        elapses; then drain up to ``max_items``."""
        with self._cond:
            if not self._buf:
                self._cond.wait(timeout=timeout)
            if not self._buf:
                return []
            batch: list[T] = []
            while self._buf and len(batch) < max_items:
                batch.append(self._buf.popleft())
            self._cond.notify_all()
            return batch

    def drain_all(self) -> list[T]:
        """Synchronously drain everything currently buffered."""
        with self._cond:
            out = list(self._buf)
            self._buf.clear()
            self._cond.notify_all()
            return out

    def __iter__(self) -> Iterator[T]:
        with self._lock:
            return iter(list(self._buf))
