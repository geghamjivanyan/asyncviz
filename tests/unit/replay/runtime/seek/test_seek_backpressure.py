"""Seek-queue backpressure tests."""

from __future__ import annotations

from asyncviz.replay.runtime.seek import SeekQueue


def test_queue_within_capacity() -> None:
    q: SeekQueue[int] = SeekQueue(capacity=4)
    assert q.offer(1) is None
    assert q.offer(2) is None
    assert len(q) == 2


def test_queue_drops_oldest_on_overflow() -> None:
    q: SeekQueue[int] = SeekQueue(capacity=2)
    q.offer(1)
    q.offer(2)
    evicted = q.offer(3)
    assert evicted == 1
    assert q.peek() == 2


def test_drain_returns_all() -> None:
    q: SeekQueue[int] = SeekQueue(capacity=4)
    q.offer(1)
    q.offer(2)
    drained = q.drain()
    assert drained == [1, 2]
    assert len(q) == 0


def test_stats_track_accepts_and_drops() -> None:
    q: SeekQueue[int] = SeekQueue(capacity=2)
    q.offer(1)
    q.offer(2)
    q.offer(3)
    stats = q.stats()
    assert stats.accepted == 3
    assert stats.dropped_oldest == 1
