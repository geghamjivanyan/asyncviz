"""Checkpoint lookup helpers for the seek coordinator.

Wraps the runtime layer's :class:`CheckpointRuntime` with a couple
of convenience accessors the coordinator uses to decide whether
reconstruction needs to read a snapshot from disk or whether an
in-memory checkpoint suffices.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState
from asyncviz.replay.runtime.replay_checkpoint_runtime import (
    Checkpoint,
    CheckpointRuntime,
)


@dataclass(frozen=True, slots=True)
class CheckpointLookup:
    """Result of asking "is there a checkpoint near this sequence?"."""

    checkpoint: Checkpoint | None
    distance_frames: int = -1
    """Sequence delta between the checkpoint and the seek target.
    ``-1`` when no checkpoint matched."""

    @property
    def exact_match(self) -> bool:
        return self.checkpoint is not None and self.distance_frames == 0


def find_nearest_checkpoint(
    checkpoints: CheckpointRuntime,
    target_sequence: int,
) -> CheckpointLookup:
    """Find the checkpoint with the highest ``sequence <= target``."""
    checkpoint = checkpoints.nearest_at_or_before(target_sequence)
    if checkpoint is None:
        return CheckpointLookup(checkpoint=None)
    return CheckpointLookup(
        checkpoint=checkpoint,
        distance_frames=max(0, target_sequence - checkpoint.sequence),
    )


def state_from_checkpoint(checkpoint: Checkpoint) -> VirtualRuntimeState:
    """Extract the :class:`VirtualRuntimeState` from a checkpoint."""
    return checkpoint.state
