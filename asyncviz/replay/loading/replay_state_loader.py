"""Snapshot → state reconstruction.

Given a target sequence, build the runtime state at that point by:

1. Finding the nearest snapshot ≤ target (via :class:`ReplaySnapshotIndex`).
2. Loading its payload as the seed state.
3. Replaying every delta-bearing frame between the snapshot capture
   and the target.

The reducer that turns frames into state is supplied by the caller —
the loader doesn't impose one. A trivial default reducer is provided
that simply collects frames into a list, which is enough for tests
and for tooling that just wants a slice of replay history.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.loading.models.frame_adapter import FrameAdapter
from asyncviz.replay.loading.replay_index import ReplayIndex
from asyncviz.replay.loading.replay_observability import get_loader_metrics
from asyncviz.replay.loading.replay_seek import (
    SeekResult,
    iter_from_cursor,
    seek_to_sequence,
)
from asyncviz.replay.loading.replay_snapshot_index import (
    ReplaySnapshotIndex,
    SnapshotEntry,
    load_snapshot_payload,
)
from asyncviz.replay.loading.replay_tracing import record_replay_trace
from asyncviz.replay.recording.recording_metadata import ChunkRecord

Reducer = Callable[[dict[str, Any], ReplayFrame], dict[str, Any]]
"""``(state, frame) -> next_state``. Must be pure + deterministic."""


def default_collecting_reducer(state: dict[str, Any], frame: ReplayFrame) -> dict[str, Any]:
    """Trivial reducer — appends each frame's canonical dict to a
    ``frames`` list. Useful as a baseline + for tests."""
    frames = list(state.get("frames", ()))
    frames.append(frame.to_dict())
    state["frames"] = frames
    return state


@dataclass(frozen=True, slots=True)
class StateReconstructionResult:
    """Outcome of reconstructing state at a target sequence."""

    target_sequence: int
    state: dict[str, Any]
    snapshot_used: SnapshotEntry | None
    frames_replayed: int
    seek_result: SeekResult


@dataclass(slots=True)
class _ReducerSink:
    state: dict[str, Any] = field(default_factory=dict)
    frames_seen: int = 0


def reconstruct_state(
    target_sequence: int,
    *,
    sequence_index: ReplayIndex,
    snapshot_index: ReplaySnapshotIndex,
    chunks: tuple[ChunkRecord, ...],
    chunk_paths: tuple[Path, ...],
    adapter: FrameAdapter,
    reducer: Reducer = default_collecting_reducer,
    strict: bool = False,
) -> StateReconstructionResult:
    """Reconstruct runtime state at ``target_sequence``.

    The function:

    * Looks up the nearest snapshot ≤ target (may be ``None``).
    * Seeds the reducer state from the snapshot payload (or ``{}``).
    * Seeks to the snapshot's ``sequence_at_capture + 1`` (or to
      sequence 1 if there's no snapshot).
    * Reduces every subsequent frame up through ``target_sequence``.
    """
    snapshot = snapshot_index.nearest_at_or_before(target_sequence)
    sink = _ReducerSink()
    if snapshot is not None:
        sink.state = load_snapshot_payload(snapshot)

    start_sequence = (
        snapshot.sequence_at_capture + 1 if snapshot is not None else 1
    )
    seek_result = seek_to_sequence(
        start_sequence,
        sequence_index=sequence_index,
        snapshot_index=snapshot_index,
        chunks=chunks,
        chunk_paths=chunk_paths,
        adapter=adapter,
        strict=strict,
    )

    cursor = seek_result.cursor
    if cursor.last_sequence > target_sequence:
        # Nothing to replay — the seek already overshot, which can
        # only happen if the recording has no frame at exactly
        # start_sequence. Snapshot alone is the answer.
        get_loader_metrics().record_state_reconstruction()
        record_replay_trace(
            "state-reconstructed",
            f"target={target_sequence} replayed=0",
        )
        return StateReconstructionResult(
            target_sequence=target_sequence,
            state=sink.state,
            snapshot_used=snapshot,
            frames_replayed=0,
            seek_result=seek_result,
        )

    # Apply the landed frame (if any) then the rest up to target.
    if (
        seek_result.landed_frame is not None
        and seek_result.landed_frame.sequence <= target_sequence
    ):
        sink.state = reducer(sink.state, seek_result.landed_frame)
        sink.frames_seen += 1
    for frame in iter_from_cursor(
        cursor,
        chunks=chunks,
        chunk_paths=chunk_paths,
        adapter=adapter,
        strict=strict,
    ):
        if frame.sequence > target_sequence:
            break
        sink.state = reducer(sink.state, frame)
        sink.frames_seen += 1

    get_loader_metrics().record_state_reconstruction()
    record_replay_trace(
        "state-reconstructed",
        f"target={target_sequence} replayed={sink.frames_seen}",
    )
    return StateReconstructionResult(
        target_sequence=target_sequence,
        state=sink.state,
        snapshot_used=snapshot,
        frames_replayed=sink.frames_seen,
        seek_result=seek_result,
    )
