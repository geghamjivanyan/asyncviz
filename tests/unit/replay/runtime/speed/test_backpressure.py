"""Speed queue backpressure tests."""

from __future__ import annotations

from asyncviz.replay.runtime.speed import SpeedQueue


def test_queue_within_capacity() -> None:
    q: SpeedQueue[int] = SpeedQueue(capacity=4)
    assert q.offer(1) is None
    assert q.offer(2) is None
    assert len(q) == 2


def test_queue_drops_oldest() -> None:
    q: SpeedQueue[int] = SpeedQueue(capacity=2)
    q.offer(1)
    q.offer(2)
    evicted = q.offer(3)
    assert evicted == 1


def test_stats() -> None:
    q: SpeedQueue[int] = SpeedQueue(capacity=2)
    q.offer(1)
    q.offer(2)
    q.offer(3)
    stats = q.stats()
    assert stats.accepted == 3
    assert stats.dropped_oldest == 1
    assert stats.depth == 2
