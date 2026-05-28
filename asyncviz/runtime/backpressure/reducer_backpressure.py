"""Reducer-side backpressure adapter.

Reducers run inside the dispatch path; if their work queue grows
unbounded under overload, the runtime backs up. The adapter:

* Holds a bounded :class:`BoundedEventChannel` per reducer domain.
* Sheds low-priority work when the channel fills.
* Tracks deferred-work counts for diagnostics.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from asyncviz.runtime.backpressure.backpressure_configuration import (
    BackpressureConfig,
    DropPolicy,
)
from asyncviz.runtime.backpressure.bounded_event_channel import (
    BoundedEventChannel,
    ChannelStats,
)


@dataclass(slots=True)
class ReducerBackpressureStats:
    name: str
    channel: ChannelStats
    deferred_work: int
    shed_count: int


class ReducerBackpressureAdapter:
    """Per-reducer bounded inbox + shed counter."""

    __slots__ = (
        "_channel",
        "_deferred",
        "_lock",
        "_name",
        "_shed_count",
    )

    def __init__(
        self,
        name: str,
        config: BackpressureConfig,
        *,
        policy: DropPolicy | None = None,
        capacity: int | None = None,
    ) -> None:
        self._name = name
        self._channel: BoundedEventChannel = BoundedEventChannel(
            f"reducer:{name}",
            capacity=capacity or config.reducer_capacity,
            policy=policy or config.reducer_drop_policy,
        )
        self._deferred = 0
        self._shed_count = 0
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def channel(self) -> BoundedEventChannel:
        return self._channel

    @property
    def pressure_ratio(self) -> float:
        return self._channel.pressure_ratio

    def offer(self, item, *, priority: int = 0):  # type: ignore[no-untyped-def]
        verdict = self._channel.offer(item, priority=priority)
        if not verdict.accepted or verdict.evicted is not None:
            with self._lock:
                self._shed_count += 1
        return verdict

    def take(self):  # type: ignore[no-untyped-def]
        return self._channel.take()

    def defer(self) -> None:
        with self._lock:
            self._deferred += 1

    def stats(self) -> ReducerBackpressureStats:
        with self._lock:
            return ReducerBackpressureStats(
                name=self._name,
                channel=self._channel.stats(),
                deferred_work=self._deferred,
                shed_count=self._shed_count,
            )

    def reset(self) -> None:
        with self._lock:
            self._deferred = 0
            self._shed_count = 0
        self._channel.clear()
