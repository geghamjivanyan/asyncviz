"""Synchronous seek engine.

Runs the reconstruction pipeline + applies the result. The engine
is *synchronous* — async coordination happens at the coordinator
layer; the engine itself reads + writes state atomically inside
one ``execute`` call so partial states are never observable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from asyncviz.replay.runtime.models.engine_cursor import EngineCursor
from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState
from asyncviz.replay.runtime.replay_checkpoint_runtime import CheckpointRuntime
from asyncviz.replay.runtime.replay_cursor_runtime import CursorRuntime
from asyncviz.replay.runtime.replay_state_store import ReplayStateStore
from asyncviz.replay.runtime.seek.models.seek_request import (
    SeekRequest,
    SeekResult,
)
from asyncviz.replay.runtime.seek.replay_seek_clock import SeekClockCoordinator
from asyncviz.replay.runtime.seek.replay_seek_observability import (
    get_seek_metrics,
)
from asyncviz.replay.runtime.seek.replay_seek_reconstruction import (
    ReconstructionOutput,
    ReconstructionPipeline,
)
from asyncviz.replay.runtime.seek.replay_seek_tracing import record_seek_trace


@dataclass(frozen=True, slots=True)
class SeekExecutionInputs:
    """Bundle the engine needs from the coordinator."""

    target_sequence: int
    request: SeekRequest


class SeekEngine:
    """One ``execute`` call applies a complete seek."""

    __slots__ = (
        "_cache_results",
        "_checkpoints",
        "_clock",
        "_cursor",
        "_pipeline",
        "_record_checkpoint",
        "_state_store",
    )

    def __init__(
        self,
        *,
        pipeline: ReconstructionPipeline,
        state_store: ReplayStateStore,
        cursor: CursorRuntime,
        clock: SeekClockCoordinator,
        checkpoints: CheckpointRuntime,
        cache_results: bool = True,
        record_checkpoint: bool = True,
    ) -> None:
        self._pipeline = pipeline
        self._state_store = state_store
        self._cursor = cursor
        self._clock = clock
        self._checkpoints = checkpoints
        self._cache_results = cache_results
        self._record_checkpoint = record_checkpoint

    def execute(self, inputs: SeekExecutionInputs) -> SeekResult:
        started_ns = time.monotonic_ns()
        target = inputs.target_sequence
        out: ReconstructionOutput = self._pipeline.reconstruct(target)

        # Bump metric counters by reconstruction path.
        metrics = get_seek_metrics()
        if out.error_detail:
            metrics.record_failed()
            record_seek_trace("seek-failed", out.error_detail)
            return SeekResult(
                request_id=inputs.request.request_id,
                target_sequence=target,
                landed_sequence=0,
                landed_monotonic_ns=0,
                used_cache=False,
                used_checkpoint=False,
                used_snapshot=False,
                frames_replayed=0,
                latency_ns=time.monotonic_ns() - started_ns,
                error_detail=out.error_detail,
            )

        if out.used_cache:
            metrics.record_cache_hit()
            record_seek_trace("cache-hit", f"seq={out.landed_sequence}")
        elif out.used_checkpoint:
            metrics.record_checkpoint_hit()
            record_seek_trace("checkpoint-hit", f"seq={out.landed_sequence}")
        elif out.used_snapshot:
            metrics.record_snapshot_hit()
            record_seek_trace("snapshot-hit", f"seq={out.landed_sequence}")
        else:
            metrics.record_full_reconstruction()
            record_seek_trace(
                "full-reconstruction", f"seq={out.landed_sequence}",
            )

        # Atomic application: state store, cursor, clock.
        self._apply(out)

        # Optional cache + checkpoint write-through.
        # Key the cache by the *target* the caller asked for so a
        # repeat seek for the same target is an O(0) hit, even when
        # reconstruction overshoots to a different landed sequence.
        if self._cache_results and not out.used_cache:
            self._pipeline.cache(
                sequence=target,
                monotonic_ns=out.landed_monotonic_ns,
                state=out.state,
            )
        if self._record_checkpoint and not out.used_checkpoint and not out.used_cache:
            self._checkpoints.record(out.state)

        latency_ns = time.monotonic_ns() - started_ns
        metrics.record_completed(
            latency_ns=latency_ns, frames_replayed=out.frames_replayed,
        )
        return SeekResult(
            request_id=inputs.request.request_id,
            target_sequence=target,
            landed_sequence=out.landed_sequence,
            landed_monotonic_ns=out.landed_monotonic_ns,
            used_cache=out.used_cache,
            used_checkpoint=out.used_checkpoint,
            used_snapshot=out.used_snapshot,
            frames_replayed=out.frames_replayed,
            latency_ns=latency_ns,
        )

    def _apply(self, out: ReconstructionOutput) -> None:
        # Force the state store to the reconstructed value — pure
        # replace so listeners see the swap as one event.
        self._state_store.replace(out.state)
        # Cursor anchored at the reconstructed sequence.
        previous_cursor: EngineCursor = self._cursor.cursor
        self._cursor.set(
            previous_cursor.jumped_to(
                sequence=out.landed_sequence,
                monotonic_ns=out.landed_monotonic_ns,
                virtual_ns=out.landed_monotonic_ns,
            ),
        )
        # Clock re-anchored at the landed frame's virtual time.
        self._clock.anchor_at(out.landed_monotonic_ns)

    @staticmethod
    def reset_to(state_store: ReplayStateStore, state: VirtualRuntimeState) -> None:
        """Helper for callers that want to drop reconstructed state
        without going through ``execute`` (e.g. seek failures)."""
        state_store.replace(state)
