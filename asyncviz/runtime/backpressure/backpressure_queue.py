"""Priority-aware bounded queue used by every backpressure
channel.

Distinct from :class:`asyncviz.replay.recording.recording_backpressure.BoundedRingBuffer`
(which is the recording-layer write-side primitive) — this queue
is reusable across the backpressure subsystem so different domains
share the same enqueue semantics.

Four drop policies:

* ``drop-newest`` — refuse the incoming item.
* ``drop-oldest`` — evict the head + accept.
* ``drop-low-priority`` — evict the lowest-priority item;
  refuse when the incoming item is itself the lowest.
* ``block`` — caller must check ``len`` themselves; ``offer``
  refuses + signals back via the verdict.
"""

from __future__ import annotations

import heapq
import itertools
import threading
from collections import deque
from dataclasses import dataclass

from asyncviz.runtime.backpressure.backpressure_configuration import DropPolicy


@dataclass(frozen=True, slots=True)
class EnqueueVerdict[T]:
    """Outcome of one ``offer`` call."""

    accepted: bool
    evicted: T | None = None
    reason: str = ""


@dataclass(slots=True)
class QueueStats:
    capacity: int
    depth: int
    accepted: int
    rejected: int
    evicted_oldest: int
    evicted_low_priority: int


class PriorityBoundedQueue[T]:
    """Drop-policy-driven bounded queue.

    For ``drop-low-priority``, items carry an integer priority
    supplied at offer time. Lower number = lower priority.
    """

    __slots__ = (
        "_accepted",
        "_buf",
        "_capacity",
        "_counter",
        "_evicted_low_priority",
        "_evicted_oldest",
        "_lock",
        "_policy",
        "_rejected",
    )

    def __init__(
        self, *, capacity: int, policy: DropPolicy,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._policy = policy
        self._lock = threading.Lock()
        # Storage: deque for FIFO policies, heap for drop-low-priority.
        if policy == "drop-low-priority":
            self._buf: list = []  # type: ignore[type-arg]
        else:
            self._buf = deque()
        self._counter = itertools.count()
        self._accepted = 0
        self._rejected = 0
        self._evicted_oldest = 0
        self._evicted_low_priority = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def policy(self) -> DropPolicy:
        return self._policy

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)

    # ── enqueue ───────────────────────────────────────────────────

    def offer(self, item: T, *, priority: int = 0) -> EnqueueVerdict[T]:
        with self._lock:
            if len(self._buf) < self._capacity:
                self._push_locked(item, priority)
                self._accepted += 1
                return EnqueueVerdict(accepted=True)

            if self._policy == "drop-newest":
                self._rejected += 1
                return EnqueueVerdict(
                    accepted=False, reason="drop-newest",
                )
            if self._policy == "block":
                self._rejected += 1
                return EnqueueVerdict(
                    accepted=False, reason="block-full",
                )
            if self._policy == "drop-oldest":
                evicted = self._pop_oldest_locked()
                self._push_locked(item, priority)
                self._evicted_oldest += 1
                self._accepted += 1
                return EnqueueVerdict(accepted=True, evicted=evicted, reason="drop-oldest")
            # drop-low-priority
            head_priority = self._peek_lowest_priority_locked()
            if head_priority is not None and priority < head_priority:
                # Incoming item is itself the lowest — refuse it.
                self._rejected += 1
                return EnqueueVerdict(
                    accepted=False, reason="drop-low-priority-incoming",
                )
            evicted = self._pop_lowest_priority_locked()
            self._push_locked(item, priority)
            self._evicted_low_priority += 1
            self._accepted += 1
            return EnqueueVerdict(
                accepted=True, evicted=evicted, reason="drop-low-priority",
            )

    # ── dequeue ───────────────────────────────────────────────────

    def take(self) -> T | None:
        with self._lock:
            if not self._buf:
                return None
            return self._pop_oldest_locked()

    def drain(self) -> list[T]:
        with self._lock:
            if self._policy == "drop-low-priority":
                items: list[T] = []
                while self._buf:
                    _priority, _counter, value = heapq.heappop(self._buf)  # type: ignore[misc]
                    items.append(value)
                return items
            items = list(self._buf)
            self._buf.clear()
            return items

    def stats(self) -> QueueStats:
        with self._lock:
            return QueueStats(
                capacity=self._capacity,
                depth=len(self._buf),
                accepted=self._accepted,
                rejected=self._rejected,
                evicted_oldest=self._evicted_oldest,
                evicted_low_priority=self._evicted_low_priority,
            )

    def clear(self) -> None:
        with self._lock:
            if self._policy == "drop-low-priority":
                self._buf = []  # type: ignore[assignment]
            else:
                self._buf.clear()

    # ── internals ─────────────────────────────────────────────────

    def _push_locked(self, item: T, priority: int) -> None:
        if self._policy == "drop-low-priority":
            # Use negative priority so heap pops the lowest first.
            heapq.heappush(
                self._buf,  # type: ignore[arg-type]
                (priority, next(self._counter), item),
            )
        else:
            self._buf.append(item)

    def _pop_oldest_locked(self) -> T:
        if self._policy == "drop-low-priority":
            # ``drop-low-priority`` is FIFO within a priority tier;
            # taking the lowest-priority head is the canonical
            # "oldest under pressure" semantics.
            _priority, _counter, value = heapq.heappop(self._buf)  # type: ignore[misc]
            return value
        return self._buf.popleft()  # type: ignore[union-attr]

    def _pop_lowest_priority_locked(self) -> T:
        # Same as _pop_oldest for the priority heap.
        _priority, _counter, value = heapq.heappop(self._buf)  # type: ignore[misc]
        return value

    def _peek_lowest_priority_locked(self) -> int | None:
        if self._policy != "drop-low-priority" or not self._buf:
            return None
        priority, _counter, _value = self._buf[0]  # type: ignore[misc]
        return priority
