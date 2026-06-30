"""Priority queue + bounded channel tests."""

from __future__ import annotations

import pytest

from asyncviz.runtime.backpressure import (
    BoundedEventChannel,
    PriorityBoundedQueue,
)


def test_drop_newest_refuses_overflow() -> None:
    q: PriorityBoundedQueue[int] = PriorityBoundedQueue(
        capacity=2,
        policy="drop-newest",
    )
    assert q.offer(1).accepted
    assert q.offer(2).accepted
    verdict = q.offer(3)
    assert not verdict.accepted
    assert verdict.reason == "drop-newest"


def test_drop_oldest_evicts_head() -> None:
    q: PriorityBoundedQueue[int] = PriorityBoundedQueue(
        capacity=2,
        policy="drop-oldest",
    )
    q.offer(1)
    q.offer(2)
    verdict = q.offer(3)
    assert verdict.accepted
    assert verdict.evicted == 1
    # Take order: 2, 3
    assert q.take() == 2
    assert q.take() == 3


def test_drop_low_priority_evicts_lowest() -> None:
    q: PriorityBoundedQueue[str] = PriorityBoundedQueue(
        capacity=2,
        policy="drop-low-priority",
    )
    q.offer("low", priority=0)
    q.offer("mid", priority=5)
    # Incoming "high" (priority=10) evicts the priority=0 item.
    verdict = q.offer("high", priority=10)
    assert verdict.accepted
    assert verdict.evicted == "low"
    drained = q.drain()
    assert set(drained) == {"mid", "high"}


def test_drop_low_priority_refuses_lower_incoming() -> None:
    q: PriorityBoundedQueue[str] = PriorityBoundedQueue(
        capacity=2,
        policy="drop-low-priority",
    )
    q.offer("mid", priority=5)
    q.offer("high", priority=10)
    verdict = q.offer("lower", priority=1)
    assert not verdict.accepted
    assert verdict.reason == "drop-low-priority-incoming"


def test_block_policy_refuses_overflow() -> None:
    q: PriorityBoundedQueue[int] = PriorityBoundedQueue(
        capacity=1,
        policy="block",
    )
    q.offer(1)
    verdict = q.offer(2)
    assert not verdict.accepted
    assert verdict.reason == "block-full"


def test_channel_tracks_overflow_count() -> None:
    ch: BoundedEventChannel = BoundedEventChannel(
        "test",
        capacity=2,
        policy="drop-oldest",
    )
    for i in range(5):
        ch.offer(i)
    assert ch.overflow_count == 3
    stats = ch.stats()
    assert stats.queue.accepted == 5
    assert stats.queue.evicted_oldest == 3


def test_channel_pressure_ratio_caps_at_capacity() -> None:
    ch: BoundedEventChannel = BoundedEventChannel(
        "test",
        capacity=4,
        policy="drop-newest",
    )
    ch.offer(1)
    ch.offer(2)
    assert ch.pressure_ratio == 0.5


def test_invalid_capacity_rejected() -> None:
    with pytest.raises(ValueError):
        PriorityBoundedQueue(capacity=0, policy="drop-oldest")
