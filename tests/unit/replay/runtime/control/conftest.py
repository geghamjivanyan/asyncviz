"""Shared fixtures for playback-coordination tests."""

from __future__ import annotations

import pytest

from asyncviz.replay.runtime import ReplayClock, ReplayScheduler
from asyncviz.replay.runtime.control import (
    ReplayPlaybackCoordinationConfig,
    ReplayPlaybackCoordinator,
    clear_coordination_trace,
    reset_coordination_metrics,
    set_coordination_trace_enabled,
)


@pytest.fixture(autouse=True)
def _reset_coordination_globals() -> None:
    reset_coordination_metrics()
    clear_coordination_trace()
    set_coordination_trace_enabled(False)


@pytest.fixture
def clock() -> ReplayClock:
    return ReplayClock(initial_speed=1.0)


@pytest.fixture
def scheduler(clock: ReplayClock) -> ReplayScheduler:
    return ReplayScheduler(clock, mode="realtime")


@pytest.fixture
def coordinator(
    clock: ReplayClock,
    scheduler: ReplayScheduler,
) -> ReplayPlaybackCoordinator:
    coord = ReplayPlaybackCoordinator(
        clock=clock,
        scheduler=scheduler,
        config=ReplayPlaybackCoordinationConfig(strict_transitions=True),
    )
    coord.mark_started()
    return coord
