"""Clock + speed + pause primitives."""

from __future__ import annotations

import asyncio

import pytest

from asyncviz.replay.runtime import (
    MAX_SPEED,
    MIN_SPEED,
    PauseController,
    ReplayClock,
    SpeedController,
)


class _FakeWallClock:
    """Deterministic monotonic counter for clock tests."""

    def __init__(self) -> None:
        self.now = 1_000_000_000  # 1 second baseline

    def __call__(self) -> int:
        return self.now

    def advance(self, ns: int) -> None:
        self.now += ns


def test_clock_advances_proportional_to_wall_time() -> None:
    wall = _FakeWallClock()
    clock = ReplayClock(wall_clock=wall)
    assert clock.current_virtual_ns() == 0
    wall.advance(1_000_000)  # +1ms
    assert clock.current_virtual_ns() == 1_000_000


def test_clock_speed_scales_virtual_progression() -> None:
    wall = _FakeWallClock()
    clock = ReplayClock(initial_speed=2.0, wall_clock=wall)
    wall.advance(1_000_000)
    assert clock.current_virtual_ns() == 2_000_000  # 2x


def test_clock_pause_freezes_virtual_time() -> None:
    wall = _FakeWallClock()
    clock = ReplayClock(wall_clock=wall)
    wall.advance(500_000)
    clock.pause()
    snap_at_pause = clock.current_virtual_ns()
    wall.advance(10_000_000)
    assert clock.current_virtual_ns() == snap_at_pause
    clock.resume()
    wall.advance(1_000_000)
    assert clock.current_virtual_ns() == snap_at_pause + 1_000_000


def test_clock_set_speed_preserves_current_virtual_time() -> None:
    wall = _FakeWallClock()
    clock = ReplayClock(initial_speed=1.0, wall_clock=wall)
    wall.advance(2_000_000)  # 2ms virtual
    before = clock.current_virtual_ns()
    clock.set_speed(4.0)
    # Same instant should read the same virtual time.
    assert clock.current_virtual_ns() == before
    wall.advance(1_000_000)
    assert clock.current_virtual_ns() == before + 4_000_000  # +1ms wall * 4


def test_clock_jump_to_reanchors() -> None:
    wall = _FakeWallClock()
    clock = ReplayClock(wall_clock=wall)
    clock.jump_to(50_000_000_000)
    assert clock.current_virtual_ns() == 50_000_000_000
    wall.advance(1_000_000)
    assert clock.current_virtual_ns() == 50_000_000_000 + 1_000_000


def test_clock_rejects_non_positive_speed() -> None:
    with pytest.raises(ValueError):
        ReplayClock(initial_speed=0)
    with pytest.raises(ValueError):
        ReplayClock(initial_speed=-1)


def test_speed_controller_clamps_to_bounds() -> None:
    clock = ReplayClock()
    speed = SpeedController(clock)
    assert speed.set(100.0) == MAX_SPEED
    assert speed.set(0.0001) == MIN_SPEED
    assert speed.set(2.0) == 2.0


def test_speed_controller_records_history() -> None:
    clock = ReplayClock()
    speed = SpeedController(clock)
    speed.set(2.0)
    speed.set(4.0)
    history = speed.history()
    assert len(history) == 2
    assert history[0].new_speed == 2.0
    assert history[1].new_speed == 4.0


def test_speed_controller_listener_fires() -> None:
    clock = ReplayClock()
    speed = SpeedController(clock)
    received = []
    speed.subscribe(lambda old, new: received.append((old, new)))
    speed.set(2.0)
    assert received == [(1.0, 2.0)]


@pytest.mark.asyncio
async def test_pause_controller_event_blocks_then_releases() -> None:
    clock = ReplayClock()
    pause = PauseController(clock)
    pause.pause()

    async def waiter():
        await asyncio.wait_for(pause.wait_until_running(), timeout=1.0)

    task = asyncio.create_task(waiter())
    await asyncio.sleep(0)  # let it block
    assert not task.done()
    pause.resume()
    await task  # should complete


@pytest.mark.asyncio
async def test_pause_controller_is_idempotent() -> None:
    clock = ReplayClock()
    pause = PauseController(clock)
    assert pause.pause() is True
    assert pause.pause() is False  # already paused
    assert pause.resume() is True
    assert pause.resume() is False  # already running
