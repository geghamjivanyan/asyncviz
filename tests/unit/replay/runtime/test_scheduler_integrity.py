"""Scheduler + integrity guard tests."""

from __future__ import annotations

import pytest

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.runtime import (
    EngineCursor,
    IntegrityViolationError,
    ReplayClock,
    ReplayScheduler,
    VirtualRuntimeState,
    check_post_dispatch,
    check_pre_dispatch,
)


def _frame(seq: int, monotonic_ns: int) -> ReplayFrame:
    return ReplayFrame.for_runtime_event(
        sequence=seq, monotonic_ns=monotonic_ns,
        payload_type="asyncio.task.created", payload={"task_id": "t"},
    )


class _FakeWall:
    def __init__(self) -> None:
        self.now = 0

    def __call__(self) -> int:
        return self.now


def test_scheduler_realtime_returns_positive_wait_for_future_frame() -> None:
    wall = _FakeWall()
    clock = ReplayClock(wall_clock=wall)
    sched = ReplayScheduler(clock, mode="realtime")
    schedule = sched.schedule(frame_monotonic_ns=2_000_000)  # 2ms in the future
    assert schedule.wait_seconds > 0
    assert schedule.behind_by_ns == 0


def test_scheduler_realtime_returns_zero_wait_when_behind() -> None:
    wall = _FakeWall()
    clock = ReplayClock(wall_clock=wall)
    clock.jump_to(5_000_000)  # virtual = 5ms
    sched = ReplayScheduler(clock, mode="realtime")
    schedule = sched.schedule(frame_monotonic_ns=1_000_000)
    assert schedule.wait_seconds == 0
    assert schedule.behind_by_ns == 4_000_000


def test_scheduler_caps_wait_at_catchup_threshold() -> None:
    wall = _FakeWall()
    clock = ReplayClock(wall_clock=wall)
    sched = ReplayScheduler(clock, mode="realtime", catch_up_threshold_seconds=0.1)
    schedule = sched.schedule(frame_monotonic_ns=10_000_000_000)  # 10s out
    assert schedule.wait_seconds <= 0.1


def test_scheduler_as_fast_as_possible_returns_zero() -> None:
    wall = _FakeWall()
    clock = ReplayClock(wall_clock=wall)
    sched = ReplayScheduler(clock, mode="as_fast_as_possible")
    schedule = sched.schedule(frame_monotonic_ns=1_000_000_000)
    assert schedule.wait_seconds == 0


def test_pre_dispatch_accepts_strictly_advancing_sequence() -> None:
    cursor = EngineCursor(last_sequence=5, last_monotonic_ns=500)
    assert check_pre_dispatch(_frame(6, 600), cursor) is None


def test_pre_dispatch_rejects_duplicate() -> None:
    cursor = EngineCursor(last_sequence=5, last_monotonic_ns=500)
    v = check_pre_dispatch(_frame(5, 500), cursor)
    assert v is not None
    assert v.kind == "duplicate"


def test_pre_dispatch_rejects_out_of_order() -> None:
    cursor = EngineCursor(last_sequence=5, last_monotonic_ns=500)
    v = check_pre_dispatch(_frame(3, 300), cursor)
    assert v is not None
    assert v.kind == "out_of_order"


def test_pre_dispatch_rejects_time_regression() -> None:
    cursor = EngineCursor(last_sequence=5, last_monotonic_ns=500)
    v = check_pre_dispatch(_frame(6, 400), cursor)
    assert v is not None
    assert v.kind == "time_regression"


def test_post_dispatch_state_must_track_frame() -> None:
    state = VirtualRuntimeState(last_sequence=5, last_monotonic_ns=500, frames_applied=5)
    assert check_post_dispatch(_frame(5, 500), state) is None
    bad = VirtualRuntimeState(last_sequence=99, last_monotonic_ns=500, frames_applied=5)
    v = check_post_dispatch(_frame(5, 500), bad)
    assert v is not None
    assert v.kind == "state_sequence_mismatch"


def test_integrity_violation_error_can_raise() -> None:
    with pytest.raises(IntegrityViolationError):
        raise IntegrityViolationError("sample")
