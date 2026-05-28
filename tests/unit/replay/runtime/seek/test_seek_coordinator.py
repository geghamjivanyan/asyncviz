"""End-to-end seek-coordinator tests."""

from __future__ import annotations

from asyncviz.replay.runtime.seek import (
    ReplaySeekCoordinator,
    SeekIntent,
    SeekState,
    get_seek_metrics_snapshot,
)


def test_seek_to_sequence_lands_on_target(
    coordinator: ReplaySeekCoordinator,
) -> None:
    result = coordinator.seek_to_sequence(5)
    assert result.error_detail == ""
    assert result.landed_sequence >= 5
    assert coordinator.state.state == SeekState.COMPLETED


def test_seek_uses_snapshot_when_available(
    coordinator: ReplaySeekCoordinator,
) -> None:
    # Snapshot exists at sequence 10; seek to 11 should use it.
    result = coordinator.seek_to_sequence(11)
    assert result.used_snapshot or result.used_checkpoint
    assert result.landed_sequence >= 10


def test_repeat_seek_hits_cache(
    coordinator: ReplaySeekCoordinator,
) -> None:
    first = coordinator.seek_to_sequence(15)
    second = coordinator.seek_to_sequence(15)
    assert not first.used_cache
    assert second.used_cache


def test_seek_to_timestamp_resolves_via_loader(
    coordinator: ReplaySeekCoordinator,
) -> None:
    result = coordinator.seek_to_timestamp(5_000_000)
    assert result.error_detail == ""
    assert result.landed_sequence >= 5


def test_seek_relative_uses_cursor(
    coordinator: ReplaySeekCoordinator,
) -> None:
    coordinator.seek_to_sequence(5)
    result = coordinator.seek_relative(3)
    assert result.landed_sequence >= 8


def test_seek_to_marker_with_resolver(
    seek_session,
) -> None:
    from asyncviz.replay.loading import ReplayEventLoader
    from asyncviz.replay.runtime import (
        CheckpointRuntime,
        CursorRuntime,
        ReducerRegistry,
        ReplayClock,
        ReplayScheduler,
        ReplayStateStore,
    )
    from asyncviz.replay.runtime.seek import ReplaySeekConfig

    loader = ReplayEventLoader.open(seek_session)
    clock = ReplayClock()
    scheduler = ReplayScheduler(clock)
    coord = ReplaySeekCoordinator(
        loader=loader,
        state_store=ReplayStateStore(),
        engine_cursor=CursorRuntime(),
        clock=clock,
        scheduler=scheduler,
        checkpoints=CheckpointRuntime(),
        reducers=ReducerRegistry(),
        config=ReplaySeekConfig(pause_before_seek=False),
        marker_resolver={"m1": 7}.__getitem__,
    )
    result = coord.seek_to_marker("m1")
    assert result.landed_sequence >= 7


def test_unknown_marker_results_in_failed_seek(coordinator: ReplaySeekCoordinator) -> None:
    result = coordinator.seek_to_marker("bogus")
    assert result.error_detail
    assert coordinator.state.state == SeekState.FAILED


def test_rebuild_at_cursor_redoes_previous_seek(
    coordinator: ReplaySeekCoordinator,
) -> None:
    coordinator.seek_to_sequence(8)
    result = coordinator.rebuild_at_cursor()
    assert result.landed_sequence >= 8


def test_metrics_record_seek_lifecycle(coordinator: ReplaySeekCoordinator) -> None:
    before = get_seek_metrics_snapshot()
    coordinator.seek_to_sequence(5)
    coordinator.seek_to_sequence(5)  # cache hit
    after = get_seek_metrics_snapshot()
    assert after.seeks_requested - before.seeks_requested == 2
    assert after.seeks_completed - before.seeks_completed == 2
    assert after.cache_hits - before.cache_hits >= 1


def test_seek_intent_object_dispatch(coordinator: ReplaySeekCoordinator) -> None:
    result = coordinator.seek(SeekIntent.to_sequence(12))
    assert result.landed_sequence >= 10
