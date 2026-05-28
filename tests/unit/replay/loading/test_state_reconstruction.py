"""Snapshot + delta replay state reconstruction tests."""

from __future__ import annotations

from pathlib import Path

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.loading import (
    ReplayEventLoader,
    default_collecting_reducer,
    get_loader_metrics_snapshot,
)


def test_default_reducer_appends_frames() -> None:
    state: dict = {}
    frame = ReplayFrame.for_runtime_event(
        sequence=1, monotonic_ns=10, payload_type="x", payload={"a": 1},
    )
    state = default_collecting_reducer(state, frame)
    assert len(state["frames"]) == 1


def test_reconstruct_state_starts_from_snapshot(canonical_session: Path) -> None:
    with ReplayEventLoader.open(canonical_session) as loader:
        result = loader.reconstruct_state_at(6)
    # snapshot was captured at seq=3 — should replay frames 4..6.
    assert result.snapshot_used is not None
    assert result.snapshot_used.sequence_at_capture == 3
    assert result.frames_replayed == 3
    # snapshot payload survives
    assert result.state["tasks"] == ["t-1", "t-2", "t-3"]
    assert result.state["tick"] == 3
    # Replayed deltas appended via the default collecting reducer.
    assert len(result.state["frames"]) == 3
    assert [f["sequence"] for f in result.state["frames"]] == [4, 5, 6]


def test_reconstruct_state_below_snapshot_replays_from_start(canonical_session: Path) -> None:
    """Targeting a sequence below the earliest snapshot should
    replay from sequence 1 with no snapshot seed."""
    with ReplayEventLoader.open(canonical_session) as loader:
        result = loader.reconstruct_state_at(2)
    assert result.snapshot_used is None
    assert result.frames_replayed == 2
    assert [f["sequence"] for f in result.state["frames"]] == [1, 2]


def test_reconstruct_state_target_at_end(canonical_session: Path) -> None:
    with ReplayEventLoader.open(canonical_session) as loader:
        result = loader.reconstruct_state_at(10)
    assert result.snapshot_used.sequence_at_capture == 3
    assert result.frames_replayed == 7  # seq 4..10
    assert result.state["tasks"] == ["t-1", "t-2", "t-3"]


def test_reconstruct_state_bumps_metric(canonical_session: Path) -> None:
    before = get_loader_metrics_snapshot().state_reconstructions
    with ReplayEventLoader.open(canonical_session) as loader:
        loader.reconstruct_state_at(5)
    after = get_loader_metrics_snapshot().state_reconstructions
    assert after - before == 1


def test_load_snapshot_payload_at_returns_dict(canonical_session: Path) -> None:
    with ReplayEventLoader.open(canonical_session) as loader:
        payload = loader.load_snapshot_payload_at(9)
    assert payload is not None
    assert payload["tasks"] == ["t-1", "t-2", "t-3"]


def test_load_snapshot_payload_below_returns_none(canonical_session: Path) -> None:
    with ReplayEventLoader.open(canonical_session) as loader:
        payload = loader.load_snapshot_payload_at(1)
    assert payload is None
