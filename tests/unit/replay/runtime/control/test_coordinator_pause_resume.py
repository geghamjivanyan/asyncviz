"""End-to-end coordinator pause/resume tests."""

from __future__ import annotations

import pytest

from asyncviz.replay.runtime.control import (
    PauseBarrierTimeoutError,
    PlaybackPhase,
    ReplayPlaybackCoordinator,
    get_coordination_metrics_snapshot,
)


@pytest.mark.asyncio
async def test_pause_after_current_frame_resolves_on_dispatch(
    coordinator: ReplayPlaybackCoordinator,
) -> None:
    barrier = coordinator.request_pause(trigger="after_current_frame")
    assert coordinator.phase == PlaybackPhase.PAUSING
    triggered = coordinator.on_frame_dispatched(sequence=1, monotonic_ns=100)
    assert triggered
    resolution = await barrier.wait(timeout=1.0)
    assert resolution.paused_at_sequence == 1
    assert resolution.paused_at_monotonic_ns == 100
    assert coordinator.phase == PlaybackPhase.PAUSED


@pytest.mark.asyncio
async def test_pause_at_sequence_defers_until_target(
    coordinator: ReplayPlaybackCoordinator,
) -> None:
    barrier = coordinator.request_pause(
        trigger="at_sequence",
        target_sequence=5,
    )
    # Frame 3 — below target, shouldn't fire.
    assert not coordinator.on_frame_dispatched(sequence=3, monotonic_ns=30)
    assert coordinator.phase == PlaybackPhase.PLAYING
    # Frame 5 — target hit; should fire.
    assert coordinator.on_frame_dispatched(sequence=5, monotonic_ns=50)
    resolution = await barrier.wait(timeout=1.0)
    assert resolution.paused_at_sequence == 5


@pytest.mark.asyncio
async def test_pause_at_timestamp_defers_until_target(
    coordinator: ReplayPlaybackCoordinator,
) -> None:
    barrier = coordinator.request_pause(
        trigger="at_timestamp",
        target_monotonic_ns=500,
    )
    assert not coordinator.on_frame_dispatched(sequence=1, monotonic_ns=100)
    assert coordinator.on_frame_dispatched(sequence=6, monotonic_ns=600)
    resolution = await barrier.wait(timeout=1.0)
    assert resolution.paused_at_monotonic_ns == 600


@pytest.mark.asyncio
async def test_resume_re_anchors_clock_and_opens_gate(
    coordinator: ReplayPlaybackCoordinator,
) -> None:
    pb = coordinator.request_pause()
    coordinator.on_frame_dispatched(sequence=1, monotonic_ns=100)
    await pb.wait(timeout=1.0)
    rb = coordinator.request_resume()
    resolution = await rb.wait(timeout=1.0)
    assert coordinator.phase == PlaybackPhase.PLAYING
    assert coordinator.gate.is_open
    assert resolution.resumed_at_sequence == 1


@pytest.mark.asyncio
async def test_pause_barrier_timeout_propagates() -> None:
    from asyncviz.replay.runtime import ReplayClock, ReplayScheduler

    clock = ReplayClock()
    scheduler = ReplayScheduler(clock)
    coord = ReplayPlaybackCoordinator(clock=clock, scheduler=scheduler)
    coord.mark_started()
    barrier = coord.request_pause(trigger="at_sequence", target_sequence=1_000_000)
    with pytest.raises(PauseBarrierTimeoutError):
        await barrier.wait(timeout=0.05)


@pytest.mark.asyncio
async def test_metrics_record_pause_and_resume(
    coordinator: ReplayPlaybackCoordinator,
) -> None:
    before = get_coordination_metrics_snapshot()
    pb = coordinator.request_pause()
    coordinator.on_frame_dispatched(sequence=1, monotonic_ns=100)
    await pb.wait(timeout=1.0)
    rb = coordinator.request_resume()
    await rb.wait(timeout=1.0)
    after = get_coordination_metrics_snapshot()
    assert after.pauses_requested - before.pauses_requested == 1
    assert after.pauses_completed - before.pauses_completed == 1
    assert after.resumes_requested - before.resumes_requested == 1
    assert after.resumes_completed - before.resumes_completed == 1
