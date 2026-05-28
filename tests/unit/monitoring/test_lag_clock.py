from __future__ import annotations

import pytest

from asyncviz.runtime.monitoring.event_loop.lag_clock import (
    LagClock,
    SystemMonotonicClock,
)
from asyncviz.runtime.monitoring.event_loop.utils.fake_clock import FakeMonotonicClock


def test_system_clock_returns_monotonic_value() -> None:
    c = SystemMonotonicClock()
    a = c.monotonic_ns()
    b = c.monotonic_ns()
    assert b >= a
    assert isinstance(a, int)


def test_lag_clock_defaults_to_system_clock() -> None:
    lc = LagClock()
    assert isinstance(lc.source, SystemMonotonicClock)


def test_lag_clock_with_fake_source() -> None:
    fake = FakeMonotonicClock(initial_ns=1_000)
    lc = LagClock(fake)
    assert lc.now_ns() == 1_000
    fake.advance(500)
    assert lc.now_ns() == 1_500


def test_elapsed_ns_clamps_negative_to_zero() -> None:
    assert LagClock.elapsed_ns(start_ns=100, end_ns=50) == 0
    assert LagClock.elapsed_ns(start_ns=50, end_ns=100) == 50


def test_seconds_to_ns_clamps_non_positive_to_zero() -> None:
    assert LagClock.seconds_to_ns(-1) == 0
    assert LagClock.seconds_to_ns(0) == 0
    assert LagClock.seconds_to_ns(0.001) == 1_000_000


def test_schedule_next_advances_by_interval() -> None:
    assert LagClock.schedule_next_ns(1_000, 500) == 1_500
    assert LagClock.schedule_next_ns(1_000, 0) == 1_000


def test_fake_clock_rejects_backward_set() -> None:
    fake = FakeMonotonicClock(initial_ns=1_000)
    with pytest.raises(ValueError, match="non-decreasing"):
        fake.set_to(500)


def test_fake_clock_rejects_negative_advance() -> None:
    fake = FakeMonotonicClock(initial_ns=0)
    with pytest.raises(ValueError, match="delta must be >= 0"):
        fake.advance(-1)


def test_now_seconds_is_derived_from_ns() -> None:
    fake = FakeMonotonicClock(initial_ns=2_500_000_000)
    lc = LagClock(fake)
    assert lc.now_seconds() == 2.5
