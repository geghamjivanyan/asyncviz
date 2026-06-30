"""End-to-end engine playback tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from asyncviz.replay.loading import ReplayEventLoader
from asyncviz.replay.runtime import (
    CollectingSink,
    PlaybackState,
    ReducerRegistry,
    ReplayEngineConfig,
    ReplayRuntimeEngine,
    domain_reducer,
    get_engine_metrics_snapshot,
)


@pytest.mark.asyncio
async def test_engine_plays_all_frames_as_fast_as_possible(
    engine_session: Path,
) -> None:
    sink = CollectingSink()
    loader = ReplayEventLoader.open(engine_session)
    cfg = ReplayEngineConfig(playback_mode="as_fast_as_possible")
    async with ReplayRuntimeEngine(loader=loader, config=cfg, sink=sink) as engine:
        await engine.play()
        await asyncio.wait_for(engine.wait_until_done(), timeout=5.0)
        await engine.stop()
    assert [f.sequence for f in sink.frames] == list(range(1, 11))
    snap = engine.snapshot()
    assert snap.state == PlaybackState.STOPPED
    assert snap.frames_dispatched == 10


@pytest.mark.asyncio
async def test_engine_reducer_evolves_domain_state(
    engine_session: Path,
) -> None:
    sink = CollectingSink()
    loader = ReplayEventLoader.open(engine_session)

    def task_reducer(domain: dict, frame) -> dict:
        domain[frame.payload["task_id"]] = True
        return domain

    reducers = ReducerRegistry()
    reducers.register(
        "asyncio.task.created",
        domain_reducer("tasks", apply=task_reducer),
    )
    cfg = ReplayEngineConfig(playback_mode="as_fast_as_possible")
    async with ReplayRuntimeEngine(
        loader=loader,
        config=cfg,
        sink=sink,
        reducers=reducers,
    ) as engine:
        await engine.play()
        await asyncio.wait_for(engine.wait_until_done(), timeout=5.0)
        await engine.stop()
    state = engine.state
    assert state.frames_applied == 10
    assert len(state.domains["tasks"]) == 10
    for i in range(1, 11):
        assert f"t-{i}" in state.domains["tasks"]


@pytest.mark.asyncio
async def test_engine_pause_freezes_dispatch(engine_session: Path) -> None:
    sink = CollectingSink()
    loader = ReplayEventLoader.open(engine_session)
    cfg = ReplayEngineConfig(playback_mode="step")
    async with ReplayRuntimeEngine(loader=loader, config=cfg, sink=sink) as engine:
        await engine.play()
        # Pause immediately. Step mode + no step calls = no frames dispatched.
        await engine.pause()
        # Give the loop a chance to observe the pause.
        await asyncio.sleep(0.05)
        await engine.stop()
    # Pause beat the first step, so the engine should have dispatched nothing.
    assert sink.frames == []


@pytest.mark.asyncio
async def test_engine_step_mode_dispatches_one_per_signal(
    engine_session: Path,
) -> None:
    sink = CollectingSink()
    loader = ReplayEventLoader.open(engine_session)
    cfg = ReplayEngineConfig(playback_mode="step")
    async with ReplayRuntimeEngine(loader=loader, config=cfg, sink=sink) as engine:
        await engine.play()
        for _ in range(3):
            engine.step()
            await asyncio.sleep(0.02)
        await engine.stop()
    assert len(sink.frames) == 3
    assert [f.sequence for f in sink.frames] == [1, 2, 3]


@pytest.mark.asyncio
async def test_engine_seek_to_sequence_restores_state(engine_session: Path) -> None:
    sink = CollectingSink()
    loader = ReplayEventLoader.open(engine_session)
    cfg = ReplayEngineConfig(playback_mode="as_fast_as_possible", websocket_enabled=False)
    async with ReplayRuntimeEngine(loader=loader, config=cfg, sink=sink) as engine:
        outcome = engine.seek_to_sequence(7)
    # Snapshot was at sequence 5 — seek should use it.
    assert outcome.used_snapshot
    assert engine.state.last_sequence >= 5
    assert engine.cursor.last_sequence >= 5


@pytest.mark.asyncio
async def test_engine_set_speed_records_change(engine_session: Path) -> None:
    loader = ReplayEventLoader.open(engine_session)
    cfg = ReplayEngineConfig(initial_speed=1.0)
    async with ReplayRuntimeEngine(loader=loader, config=cfg) as engine:
        engine.set_speed(2.0)
        assert engine.clock.speed == 2.0
        engine.set_speed(0.5)
        assert engine.clock.speed == 0.5


@pytest.mark.asyncio
async def test_engine_metrics_track_lifecycle(engine_session: Path) -> None:
    loader = ReplayEventLoader.open(engine_session)
    cfg = ReplayEngineConfig(playback_mode="as_fast_as_possible")
    before = get_engine_metrics_snapshot()
    async with ReplayRuntimeEngine(loader=loader, config=cfg) as engine:
        await engine.play()
        await asyncio.wait_for(engine.wait_until_done(), timeout=5.0)
        await engine.stop()
    after = get_engine_metrics_snapshot()
    assert after.engines_started - before.engines_started == 1
    assert after.engines_stopped - before.engines_stopped == 1
    assert after.frames_dispatched - before.frames_dispatched == 10


@pytest.mark.asyncio
async def test_engine_realtime_dispatch_completes_under_speed(
    engine_session: Path,
) -> None:
    """At 32x speed, 10 ms-spaced frames should finish well under
    a second. We assert the loop *finishes*, not a timing bound."""
    sink = CollectingSink()
    loader = ReplayEventLoader.open(engine_session)
    cfg = ReplayEngineConfig(initial_speed=32.0, playback_mode="realtime")
    async with ReplayRuntimeEngine(loader=loader, config=cfg, sink=sink) as engine:
        await engine.play()
        await asyncio.wait_for(engine.wait_until_done(), timeout=2.0)
        await engine.stop()
    assert [f.sequence for f in sink.frames] == list(range(1, 11))


@pytest.mark.asyncio
async def test_engine_dispatches_through_router(engine_session: Path) -> None:
    loader = ReplayEventLoader.open(engine_session)
    cfg = ReplayEngineConfig(playback_mode="as_fast_as_possible")
    received: list[int] = []
    async with ReplayRuntimeEngine(loader=loader, config=cfg) as engine:
        engine.router.subscribe("*", lambda f: received.append(f.sequence))
        await engine.play()
        await asyncio.wait_for(engine.wait_until_done(), timeout=5.0)
        await engine.stop()
    assert received == list(range(1, 11))


@pytest.mark.asyncio
async def test_engine_checkpoint_recorded_every_interval(engine_session: Path) -> None:
    loader = ReplayEventLoader.open(engine_session)
    cfg = ReplayEngineConfig(
        playback_mode="as_fast_as_possible",
        checkpoint_interval_frames=3,
    )
    async with ReplayRuntimeEngine(loader=loader, config=cfg) as engine:
        await engine.play()
        await asyncio.wait_for(engine.wait_until_done(), timeout=5.0)
        await engine.stop()
    cps = engine.checkpoints.all()
    # 10 frames @ interval 3 => checkpoints at frames 3, 6, 9
    sequences = {cp.sequence for cp in cps}
    assert {3, 6, 9}.issubset(sequences)
