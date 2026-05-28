"""Clock-coordinator tests."""

from __future__ import annotations

from asyncviz.replay.runtime import ReplayClock
from asyncviz.replay.runtime.control import ClockCoordinator


def test_pause_resume_records_anchors() -> None:
    clock = ReplayClock()
    coord = ClockCoordinator(clock)
    pause = coord.pause()
    assert clock.paused
    assert coord.last_pause_state is not None
    assert coord.last_pause_state.paused_at_virtual_ns >= 0
    resume = coord.resume()
    assert not clock.paused
    assert resume.pause_duration_wall_ns >= 0
    assert coord.last_pause_state is None
    _ = pause  # silence unused


def test_double_pause_is_idempotent() -> None:
    clock = ReplayClock()
    coord = ClockCoordinator(clock)
    coord.pause()
    coord.pause()  # no error, no double-pause inside the clock
    assert clock.paused


def test_jump_to_refreshes_paused_anchor() -> None:
    clock = ReplayClock()
    coord = ClockCoordinator(clock)
    coord.pause()
    coord.jump_to(123_456_789)
    assert coord.last_pause_state is not None
    assert coord.last_pause_state.paused_at_virtual_ns == 123_456_789
