from __future__ import annotations

import pytest

from asyncviz.runtime.replay.recorder.replay_backpressure import (
    BackpressureMode,
    BoundedRecordQueue,
)


def test_accepts_when_under_capacity() -> None:
    q = BoundedRecordQueue(capacity=3, mode=BackpressureMode.DROP_NEWEST)
    for i in range(3):
        result = q.offer(i)
        assert result.accepted
    assert len(q) == 3


def test_drop_newest_keeps_oldest() -> None:
    q = BoundedRecordQueue(capacity=2, mode=BackpressureMode.DROP_NEWEST)
    q.offer("a")
    q.offer("b")
    out = q.offer("c")
    assert not out.accepted
    assert out.dropped_count == 1
    assert q.drain(10) == ["a", "b"]
    assert q.total_dropped == 1


def test_drop_oldest_evicts_oldest() -> None:
    q = BoundedRecordQueue(capacity=2, mode=BackpressureMode.DROP_OLDEST)
    q.offer("a")
    q.offer("b")
    out = q.offer("c")
    assert out.accepted
    assert out.dropped_was_oldest
    assert q.drain(10) == ["b", "c"]


def test_wait_for_item_returns_quickly_when_item_present() -> None:
    q = BoundedRecordQueue(capacity=2, mode=BackpressureMode.DROP_NEWEST)
    q.offer("x")
    assert q.wait_for_item(timeout=0.01) is True


def test_capacity_must_be_positive() -> None:
    with pytest.raises(ValueError):
        BoundedRecordQueue(capacity=0, mode=BackpressureMode.DROP_NEWEST)
