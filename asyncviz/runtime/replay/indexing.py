"""Replay-batch + window construction helpers.

Pure functions over the working state — kept apart from
:class:`EventReplayBuffer` so the algorithms have one home.
"""

from __future__ import annotations

from asyncviz.runtime.replay.checkpoints import ReplayCheckpoint
from asyncviz.runtime.replay.frames import ReplayFrame
from asyncviz.runtime.replay.models import (
    ReplayBatchModel,
    ReplayCheckpointModel,
    ReplayFrameModel,
    ReplayWindowModel,
)


def frame_to_model(frame: ReplayFrame) -> ReplayFrameModel:
    return ReplayFrameModel(
        sequence=frame.sequence,
        event_id=frame.event_id,
        event_type=frame.event_type,
        monotonic_ns=frame.monotonic_ns,
        wall_seconds=frame.wall_seconds,
        runtime_id=frame.runtime_id,
        task_id=frame.task_id,
        parent_task_id=frame.parent_task_id,
        payload=dict(frame.payload),
    )


def checkpoint_to_model(checkpoint: ReplayCheckpoint) -> ReplayCheckpointModel:
    return ReplayCheckpointModel(
        checkpoint_id=checkpoint.checkpoint_id,
        sequence=checkpoint.sequence,
        monotonic_ns=checkpoint.monotonic_ns,
        wall_seconds=checkpoint.wall_seconds,
        runtime_id=checkpoint.runtime_id,
        state=checkpoint.state,
        timeline=checkpoint.timeline,
        metrics=checkpoint.metrics,
        warnings=checkpoint.warnings,
        label=checkpoint.label,
    )


def build_window(
    *,
    requested_since: int,
    requested_end: int | None,
    frames: tuple[ReplayFrame, ...],
    hit: bool,
    oldest_available: int | None,
    newest_available: int | None,
) -> ReplayWindowModel:
    return ReplayWindowModel(
        requested_since=requested_since,
        requested_end=requested_end,
        hit=hit,
        oldest_available_sequence=oldest_available,
        newest_available_sequence=newest_available,
        frames=[frame_to_model(f) for f in frames],
    )


def build_batch(
    *,
    window: ReplayWindowModel,
    checkpoint: ReplayCheckpoint | None,
) -> ReplayBatchModel:
    return ReplayBatchModel(
        window=window,
        checkpoint=checkpoint_to_model(checkpoint) if checkpoint is not None else None,
    )
