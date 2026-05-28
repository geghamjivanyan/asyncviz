"""Single-frame stepping tests."""

from __future__ import annotations

import pytest

from asyncviz.replay.runtime.control import (
    PlaybackPhase,
    ReplayPlaybackCoordinator,
)


@pytest.mark.asyncio
async def test_step_from_paused_dispatches_one_frame(
    coordinator: ReplayPlaybackCoordinator,
) -> None:
    pb = coordinator.request_pause()
    coordinator.on_frame_dispatched(sequence=1, monotonic_ns=100)
    await pb.wait(timeout=1.0)
    assert coordinator.phase == PlaybackPhase.PAUSED
    coordinator.request_step(frames=1)
    assert coordinator.phase == PlaybackPhase.STEPPING
    assert coordinator.pending_step_frames == 1
    # Engine "dispatches" one frame.
    assert coordinator.consume_step()
    assert coordinator.pending_step_frames == 0
    triggered = coordinator.on_frame_dispatched(sequence=2, monotonic_ns=200)
    assert triggered
    assert coordinator.phase == PlaybackPhase.PAUSED


@pytest.mark.asyncio
async def test_multi_frame_step_burst(
    coordinator: ReplayPlaybackCoordinator,
) -> None:
    pb = coordinator.request_pause()
    coordinator.on_frame_dispatched(sequence=1, monotonic_ns=100)
    await pb.wait(timeout=1.0)
    coordinator.request_step(frames=3)
    assert coordinator.pending_step_frames == 3
    consumed = [coordinator.consume_step() for _ in range(3)]
    assert consumed == [True, True, True]
    assert not coordinator.consume_step()
    coordinator.on_frame_dispatched(sequence=4, monotonic_ns=400)
    assert coordinator.phase == PlaybackPhase.PAUSED


@pytest.mark.asyncio
async def test_step_rejects_zero_frames(coordinator: ReplayPlaybackCoordinator) -> None:
    pb = coordinator.request_pause()
    coordinator.on_frame_dispatched(sequence=1, monotonic_ns=100)
    await pb.wait(timeout=1.0)
    with pytest.raises(ValueError):
        coordinator.request_step(frames=0)
