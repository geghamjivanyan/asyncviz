from __future__ import annotations

import pytest

from asyncviz.runtime.monitoring.event_loop.lag_backpressure import (
    LagMonitorBackpressure,
)


def test_uncapped_backpressure_accepts_all() -> None:
    bp = LagMonitorBackpressure(capacity=0)
    for _ in range(100):
        d = bp.acquire()
        assert d.accepted is True
        assert d.reason == "uncapped"
    assert bp.pending == 100
    assert bp.denied == 0


def test_capacity_enforced() -> None:
    bp = LagMonitorBackpressure(capacity=2)
    a = bp.acquire()
    b = bp.acquire()
    c = bp.acquire()
    assert a.accepted is True
    assert b.accepted is True
    assert c.accepted is False
    assert c.reason == "capacity_exceeded"
    assert bp.denied == 1
    assert bp.pending == 2


def test_release_lets_new_acquires_through() -> None:
    bp = LagMonitorBackpressure(capacity=1)
    a = bp.acquire()
    assert a.accepted is True
    b = bp.acquire()
    assert b.accepted is False
    bp.release()
    c = bp.acquire()
    assert c.accepted is True


def test_release_under_zero_pending_is_safe() -> None:
    bp = LagMonitorBackpressure(capacity=1)
    bp.release()
    bp.release()
    assert bp.pending == 0


def test_reset_clears_pending_and_denied() -> None:
    bp = LagMonitorBackpressure(capacity=1)
    bp.acquire()
    bp.acquire()  # denied
    bp.reset()
    assert bp.pending == 0
    assert bp.denied == 0


def test_capacity_must_be_non_negative() -> None:
    with pytest.raises(ValueError, match="capacity must be >= 0"):
        LagMonitorBackpressure(capacity=-1)
