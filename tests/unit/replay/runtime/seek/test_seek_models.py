"""Model + projection tests."""

from __future__ import annotations

from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState
from asyncviz.replay.runtime.seek import (
    SeekCursor,
    SeekIntent,
    SeekResult,
    SeekState,
    SeekStateSnapshot,
    project_seek,
)


def test_seek_intent_factories() -> None:
    assert SeekIntent.to_sequence(42) == SeekIntent(
        kind="sequence",
        target_sequence=42,
    )
    assert SeekIntent.to_timestamp(99).kind == "timestamp"
    assert SeekIntent.to_marker("m1").kind == "marker"
    assert SeekIntent.relative(-5).kind == "relative"


def test_seek_state_snapshot_in_flight_predicate() -> None:
    assert SeekStateSnapshot(state=SeekState.RECONSTRUCTING).is_in_flight
    assert SeekStateSnapshot(state=SeekState.APPLYING).is_in_flight
    assert SeekStateSnapshot(state=SeekState.QUEUED).is_in_flight
    assert not SeekStateSnapshot(state=SeekState.IDLE).is_in_flight
    assert not SeekStateSnapshot(state=SeekState.COMPLETED).is_in_flight


def test_seek_state_snapshot_terminal_predicate() -> None:
    assert SeekStateSnapshot(state=SeekState.COMPLETED).is_terminal
    assert SeekStateSnapshot(state=SeekState.CANCELLED).is_terminal
    assert SeekStateSnapshot(state=SeekState.FAILED).is_terminal
    assert not SeekStateSnapshot(state=SeekState.RECONSTRUCTING).is_terminal


def test_seek_cursor_advance() -> None:
    cursor = SeekCursor.at_start()
    advanced = cursor.advance(sequence=5, monotonic_ns=500, request_id=1)
    assert advanced.last_seek_sequence == 5
    assert advanced.seeks_completed == 1


def test_project_seek_overshoot() -> None:
    result = SeekResult(
        request_id=1,
        target_sequence=10,
        landed_sequence=12,
        landed_monotonic_ns=120,
        used_cache=False,
        used_checkpoint=False,
        used_snapshot=True,
        frames_replayed=12,
        latency_ns=500_000,
    )
    state = VirtualRuntimeState(domains={"tasks": {}, "queues": {}})
    projection = project_seek(result=result, state=state)
    assert projection.overshoot == 2
    assert projection.domains_present == ("queues", "tasks")
    assert projection.latency_ms == 0.5
