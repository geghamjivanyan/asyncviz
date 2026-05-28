"""Coordination-queue backpressure tests."""

from __future__ import annotations

from asyncviz.replay.runtime.control import CoordinationQueue


def test_queue_accepts_within_capacity() -> None:
    q: CoordinationQueue[int] = CoordinationQueue(capacity=3)
    assert q.offer(1) is None
    assert q.offer(2) is None
    assert q.offer(3) is None
    assert len(q) == 3


def test_queue_drops_oldest_on_overflow() -> None:
    q: CoordinationQueue[int] = CoordinationQueue(capacity=2)
    q.offer(1)
    q.offer(2)
    evicted = q.offer(3)
    assert evicted == 1
    assert q.peek() == 2


def test_stats_track_accepts_and_drops() -> None:
    q: CoordinationQueue[int] = CoordinationQueue(capacity=2)
    q.offer(1)
    q.offer(2)
    q.offer(3)
    stats = q.stats()
    assert stats.accepted == 3
    assert stats.dropped_oldest == 1
    assert stats.depth == 2
    assert stats.capacity == 2


def test_drain_returns_all_items() -> None:
    q: CoordinationQueue[int] = CoordinationQueue(capacity=4)
    q.offer(1)
    q.offer(2)
    q.offer(3)
    drained = q.drain()
    assert drained == [1, 2, 3]
    assert len(q) == 0
