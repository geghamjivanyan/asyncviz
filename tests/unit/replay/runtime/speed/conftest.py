"""Shared fixtures for replay-speed tests."""

from __future__ import annotations

import pytest

from asyncviz.replay.runtime import ReplayClock, ReplayScheduler
from asyncviz.replay.runtime.speed import (
    ReplaySpeedConfig,
    ReplaySpeedController,
    clear_speed_trace,
    reset_speed_metrics,
    set_speed_trace_enabled,
)


@pytest.fixture(autouse=True)
def _reset_speed_globals() -> None:
    reset_speed_metrics()
    clear_speed_trace()
    set_speed_trace_enabled(False)


@pytest.fixture
def clock() -> ReplayClock:
    return ReplayClock(initial_speed=1.0)


@pytest.fixture
def scheduler(clock: ReplayClock) -> ReplayScheduler:
    return ReplayScheduler(clock)


@pytest.fixture
def controller(
    clock: ReplayClock,
    scheduler: ReplayScheduler,
) -> ReplaySpeedController:
    return ReplaySpeedController(
        clock=clock,
        scheduler=scheduler,
        config=ReplaySpeedConfig(),
    )
