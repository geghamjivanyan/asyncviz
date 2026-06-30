"""Bounded event channel wrapping the priority queue.

The channel is the per-subsystem inbox: a producer calls
``offer()``, a consumer calls ``take()`` / ``drain()``. The
:class:`EventBackpressureController` consults a channel's queue
depth via :attr:`pressure_ratio` when computing the global
overload state.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.backpressure.backpressure_configuration import DropPolicy
from asyncviz.runtime.backpressure.backpressure_queue import (
    EnqueueVerdict,
    PriorityBoundedQueue,
    QueueStats,
)


@dataclass(frozen=True, slots=True)
class ChannelStats:
    name: str
    queue: QueueStats
    overflow_count: int


class BoundedEventChannel[T]:
    """One bounded per-subsystem channel."""

    __slots__ = ("_name", "_overflow_count", "_queue")

    def __init__(
        self,
        name: str,
        *,
        capacity: int,
        policy: DropPolicy,
    ) -> None:
        self._name = name
        self._queue: PriorityBoundedQueue[T] = PriorityBoundedQueue(
            capacity=capacity,
            policy=policy,
        )
        self._overflow_count = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def capacity(self) -> int:
        return self._queue.capacity

    @property
    def policy(self) -> DropPolicy:
        return self._queue.policy

    @property
    def depth(self) -> int:
        return len(self._queue)

    @property
    def pressure_ratio(self) -> float:
        cap = self._queue.capacity
        if cap <= 0:
            return 0.0
        return len(self._queue) / cap

    @property
    def overflow_count(self) -> int:
        return self._overflow_count

    def offer(self, item: T, *, priority: int = 0) -> EnqueueVerdict[T]:
        verdict = self._queue.offer(item, priority=priority)
        if not verdict.accepted or verdict.evicted is not None:
            self._overflow_count += 1
        return verdict

    def take(self) -> T | None:
        return self._queue.take()

    def drain(self) -> list[T]:
        return self._queue.drain()

    def stats(self) -> ChannelStats:
        return ChannelStats(
            name=self._name,
            queue=self._queue.stats(),
            overflow_count=self._overflow_count,
        )

    def clear(self) -> None:
        self._queue.clear()
        self._overflow_count = 0
