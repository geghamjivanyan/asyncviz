"""Checkpoint + snapshot-runtime tests."""

from __future__ import annotations

from pathlib import Path

from asyncviz.replay.loading import ReplayEventLoader
from asyncviz.replay.runtime import (
    CheckpointRuntime,
    ReplayStateStore,
    SnapshotRuntime,
    VirtualRuntimeState,
)


def test_checkpoint_runtime_keeps_capacity_bounded() -> None:
    cp_rt = CheckpointRuntime(capacity=3)
    for i in range(1, 6):
        cp_rt.record(
            VirtualRuntimeState(last_sequence=i, last_monotonic_ns=i, frames_applied=i),
        )
    assert cp_rt.size == 3
    sequences = [cp.sequence for cp in cp_rt.all()]
    assert sequences == [3, 4, 5]


def test_checkpoint_runtime_finds_nearest_at_or_before() -> None:
    cp_rt = CheckpointRuntime(capacity=10)
    for i in (5, 10, 15):
        cp_rt.record(
            VirtualRuntimeState(last_sequence=i, last_monotonic_ns=i, frames_applied=i),
        )
    assert cp_rt.nearest_at_or_before(11).sequence == 10
    assert cp_rt.nearest_at_or_before(15).sequence == 15
    assert cp_rt.nearest_at_or_before(3) is None


def test_snapshot_runtime_restores_state_from_disk(engine_session: Path) -> None:
    loader = ReplayEventLoader.open(engine_session)
    store = ReplayStateStore()
    snap_rt = SnapshotRuntime(loader.snapshot_index, store)
    # Snapshot was captured at sequence 5.
    result = snap_rt.restore_for_sequence(7)
    assert result.snapshot is not None
    assert result.snapshot.sequence_at_capture == 5
    assert result.resumed_from_sequence == 6
    assert store.state.last_sequence == 5
    assert "tasks" in store.state.domains


def test_snapshot_runtime_no_snapshot_below_resets_state(engine_session: Path) -> None:
    loader = ReplayEventLoader.open(engine_session)
    store = ReplayStateStore(initial=VirtualRuntimeState(last_sequence=99))
    snap_rt = SnapshotRuntime(loader.snapshot_index, store)
    result = snap_rt.restore_for_sequence(1)  # snapshot is at 5 — no earlier
    assert result.snapshot is None
    assert result.resumed_from_sequence == 1
    assert store.state == VirtualRuntimeState.empty()
