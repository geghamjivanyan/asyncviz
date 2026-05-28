"""Clock coordinator + drift sampling tests."""

from __future__ import annotations

from asyncviz.replay.runtime import ReplayClock
from asyncviz.replay.runtime.speed import SpeedClockCoordinator


class _FakeWall:
    def __init__(self) -> None:
        self.now = 0

    def __call__(self) -> int:
        return self.now


def test_apply_speed_refreshes_anchor() -> None:
    wall = _FakeWall()
    clock = ReplayClock(wall_clock=wall)
    coord = SpeedClockCoordinator(clock, wall_clock=wall)
    anchor1 = coord.anchor
    coord.apply_speed(2.0)
    anchor2 = coord.anchor
    assert anchor2.speed == 2.0
    assert anchor2.virtual_ns == clock.current_virtual_ns()
    assert anchor2.wall_ns >= anchor1.wall_ns


def test_drift_sample_is_zero_under_clock_invariant() -> None:
    wall = _FakeWall()
    clock = ReplayClock(wall_clock=wall)
    coord = SpeedClockCoordinator(clock, wall_clock=wall)
    wall.now += 1_000_000  # 1 ms wall elapsed
    sample = coord.sample_drift()
    # The clock's own virtual progression matches expected — zero drift.
    assert sample.drift_ns == 0


def test_drift_sample_reflects_external_clock_jump() -> None:
    wall = _FakeWall()
    clock = ReplayClock(wall_clock=wall)
    coord = SpeedClockCoordinator(clock, wall_clock=wall)
    # Externally jump the clock — simulates a seek bypassing the
    # speed coordinator's awareness.
    clock.jump_to(999_999_999)
    sample = coord.sample_drift()
    assert sample.drift_ns != 0


def test_re_anchor_from_seek_clears_drift() -> None:
    wall = _FakeWall()
    clock = ReplayClock(wall_clock=wall)
    coord = SpeedClockCoordinator(clock, wall_clock=wall)
    clock.jump_to(999_999_999)
    coord.re_anchor_from_seek(999_999_999)
    sample = coord.sample_drift()
    assert sample.drift_ns == 0
