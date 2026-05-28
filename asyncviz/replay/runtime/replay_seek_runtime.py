"""Engine-side seek + state reconstruction.

Wraps the loader's seek primitives + the engine's snapshot +
checkpoint primitives so a seek always:

1. Picks the nearest checkpoint ≤ target (in-memory, cheap).
2. Falls back to the nearest snapshot ≤ target (disk read).
3. Resumes from there, replaying frames through the reducer to
   reach the target sequence.
4. Atomically jumps the clock + cursor + state store so playback
   can resume from a coherent point.

Bounded seek latency: in the best case (checkpoint exists for
target), reconstruction is O(0). In the worst case (no snapshot,
seek to a far-out sequence) the cost is the loader's normal
state-reconstruction walk.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.loading import (
    ReplayEventLoader,
    StateReconstructionResult,
)
from asyncviz.replay.runtime.models.engine_cursor import EngineCursor
from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState
from asyncviz.replay.runtime.replay_checkpoint_runtime import CheckpointRuntime
from asyncviz.replay.runtime.replay_clock import ReplayClock
from asyncviz.replay.runtime.replay_cursor_runtime import CursorRuntime
from asyncviz.replay.runtime.replay_reducers import ReducerRegistry
from asyncviz.replay.runtime.replay_state_store import ReplayStateStore


@dataclass(frozen=True, slots=True)
class SeekOutcome:
    """Result of an engine-level seek."""

    target_sequence: int
    used_checkpoint: bool
    used_snapshot: bool
    landed_frame: ReplayFrame | None
    final_state: VirtualRuntimeState
    final_cursor: EngineCursor
    frames_replayed: int


class ReplaySeekRuntime:
    """Composes loader seek + engine state into one operation."""

    __slots__ = (
        "_checkpoints",
        "_clock",
        "_cursor",
        "_loader",
        "_reducers",
        "_state_store",
    )

    def __init__(
        self,
        *,
        loader: ReplayEventLoader,
        reducers: ReducerRegistry,
        state_store: ReplayStateStore,
        cursor: CursorRuntime,
        clock: ReplayClock,
        checkpoints: CheckpointRuntime,
    ) -> None:
        self._loader = loader
        self._reducers = reducers
        self._state_store = state_store
        self._cursor = cursor
        self._clock = clock
        self._checkpoints = checkpoints

    def seek_to_sequence(self, target_sequence: int) -> SeekOutcome:
        """Try the in-memory checkpoint first; fall back to loader-
        driven reconstruction. Either path leaves the state store +
        cursor + clock anchored at the seek target."""
        checkpoint = self._checkpoints.nearest_at_or_before(target_sequence)
        if checkpoint is not None and checkpoint.sequence == target_sequence:
            return self._restore_from_checkpoint_exact(checkpoint)
        return self._restore_via_loader(target_sequence)

    # ── internals ─────────────────────────────────────────────────

    def _restore_from_checkpoint_exact(
        self,
        checkpoint,  # type: ignore[no-untyped-def]
    ) -> SeekOutcome:
        state = self._state_store.replace(checkpoint.state)
        new_cursor = self._cursor.cursor.jumped_to(
            sequence=checkpoint.sequence,
            monotonic_ns=checkpoint.monotonic_ns,
            virtual_ns=checkpoint.monotonic_ns,
        )
        self._cursor.set(new_cursor)
        self._clock.jump_to(checkpoint.monotonic_ns)
        return SeekOutcome(
            target_sequence=checkpoint.sequence,
            used_checkpoint=True,
            used_snapshot=False,
            landed_frame=None,
            final_state=state,
            final_cursor=new_cursor,
            frames_replayed=0,
        )

    def _restore_via_loader(self, target_sequence: int) -> SeekOutcome:
        reconstruction: StateReconstructionResult = self._loader.reconstruct_state_at(
            target_sequence,
            reducer=_state_reducer_adapter(self._reducers),
        )
        # Convert the loader's dict-state back into our domain shape.
        # The reducer adapter has been writing through a wrapper so
        # the loader hands us a VirtualRuntimeState-equivalent dict.
        next_state = VirtualRuntimeState.from_dict(reconstruction.state)
        if reconstruction.snapshot_used is not None:
            snap_seq = reconstruction.snapshot_used.sequence_at_capture
            next_state = VirtualRuntimeState(
                last_sequence=next_state.last_sequence or snap_seq,
                last_monotonic_ns=next_state.last_monotonic_ns,
                frames_applied=next_state.frames_applied,
                domains=next_state.domains,
                notes=next_state.notes,
            )
        state = self._state_store.replace(next_state)
        landed_seq = (
            reconstruction.seek_result.landed_frame.sequence
            if reconstruction.seek_result.landed_frame is not None
            else target_sequence
        )
        landed_ns = (
            reconstruction.seek_result.landed_frame.monotonic_ns
            if reconstruction.seek_result.landed_frame is not None
            else state.last_monotonic_ns
        )
        new_cursor = self._cursor.cursor.jumped_to(
            sequence=landed_seq,
            monotonic_ns=landed_ns,
            virtual_ns=landed_ns,
        )
        self._cursor.set(new_cursor)
        self._clock.jump_to(landed_ns)
        return SeekOutcome(
            target_sequence=target_sequence,
            used_checkpoint=False,
            used_snapshot=reconstruction.snapshot_used is not None,
            landed_frame=reconstruction.seek_result.landed_frame,
            final_state=state,
            final_cursor=new_cursor,
            frames_replayed=reconstruction.frames_replayed,
        )


def _state_reducer_adapter(registry: ReducerRegistry):
    """The loader's reducer signature is ``(dict, frame) -> dict``;
    ours is ``(VirtualRuntimeState, frame) -> VirtualRuntimeState``.
    This shim converts both ways so the loader's reconstruction path
    can drive our reducer registry."""

    def _reduce(state_dict: dict, frame: ReplayFrame) -> dict:
        state = (
            VirtualRuntimeState.from_dict(state_dict)
            if state_dict
            else VirtualRuntimeState.empty()
        )
        next_state = registry.apply(state, frame)
        return next_state.to_dict()

    return _reduce
