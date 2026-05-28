"""Race-condition + storm simulations.

Rapid pause/resume bursts must remain deterministic — the
coordinator's drop-oldest queue keeps the engine sane under
mash-the-button input.
"""

from __future__ import annotations

import pytest

from asyncviz.replay.runtime.control import (
    PlaybackPhase,
    ReplayPlaybackCoordinationConfig,
    ReplayPlaybackCoordinator,
)


@pytest.mark.asyncio
async def test_rapid_pause_storm_collapses_to_one_paused_state() -> None:
    from asyncviz.replay.runtime import ReplayClock, ReplayScheduler

    clock = ReplayClock()
    scheduler = ReplayScheduler(clock)
    coord = ReplayPlaybackCoordinator(
        clock=clock,
        scheduler=scheduler,
        config=ReplayPlaybackCoordinationConfig(coordination_queue_capacity=4),
    )
    coord.mark_started()
    # Mash the pause button 20 times.
    barriers = [coord.request_pause() for _ in range(20)]
    # Engine acknowledges with a single frame dispatch.
    coord.on_frame_dispatched(sequence=1, monotonic_ns=100)
    # Surviving barriers (within queue capacity) resolve; others
    # were cancelled by the drop-oldest queue.
    resolved = 0
    for barrier in barriers:
        if barrier.resolved:
            resolved += 1
    assert resolved >= 1
    assert coord.phase == PlaybackPhase.PAUSED


@pytest.mark.asyncio
async def test_rapid_pause_resume_oscillation_settles_to_playing() -> None:
    from asyncviz.replay.runtime import ReplayClock, ReplayScheduler

    clock = ReplayClock()
    scheduler = ReplayScheduler(clock)
    coord = ReplayPlaybackCoordinator(clock=clock, scheduler=scheduler)
    coord.mark_started()
    for _ in range(10):
        pb = coord.request_pause()
        coord.on_frame_dispatched(sequence=1, monotonic_ns=100)
        await pb.wait(timeout=1.0)
        rb = coord.request_resume()
        await rb.wait(timeout=1.0)
    assert coord.phase == PlaybackPhase.PLAYING


@pytest.mark.asyncio
async def test_pause_idempotent_when_already_paused(
    coordinator: ReplayPlaybackCoordinator,
) -> None:
    pb = coordinator.request_pause()
    coordinator.on_frame_dispatched(sequence=1, monotonic_ns=100)
    await pb.wait(timeout=1.0)
    # Request another pause — should resolve immediately (already paused).
    pb2 = coordinator.request_pause()
    # Engine dispatches another acknowledgement, which the queue is
    # already idempotent about.
    coordinator.on_frame_dispatched(sequence=2, monotonic_ns=200)
    res = await pb2.wait(timeout=1.0)
    assert res.paused_at_sequence >= 1
