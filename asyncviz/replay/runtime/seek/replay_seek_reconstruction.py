"""Reconstruction pipeline.

Walks the three-tier strategy:

1. **Cache hit** — :class:`SeekCache` returns the state directly.
2. **Checkpoint hit** — :class:`CheckpointRuntime` returns a state ≤
   target; we replay deltas from there.
3. **Snapshot / loader** — fall back to
   :class:`ReplaySeekRuntime.seek_to_sequence` which handles
   snapshot lookup + delta replay.

This module is the single place every "rebuild the state" call
goes through, so the coordinator can stay focused on transition +
queue concerns.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState
from asyncviz.replay.runtime.replay_checkpoint_runtime import CheckpointRuntime
from asyncviz.replay.runtime.replay_seek_runtime import (
    ReplaySeekRuntime,
    SeekOutcome,
)
from asyncviz.replay.runtime.seek.replay_seek_cache import (
    SeekCache,
    SeekCacheEntry,
)
from asyncviz.replay.runtime.seek.replay_seek_checkpoint import (
    CheckpointLookup,
    find_nearest_checkpoint,
)


@dataclass(frozen=True, slots=True)
class ReconstructionOutput:
    """Result of one reconstruction call."""

    state: VirtualRuntimeState
    landed_sequence: int
    landed_monotonic_ns: int
    used_cache: bool
    used_checkpoint: bool
    used_snapshot: bool
    frames_replayed: int
    elapsed_ns: int
    error_detail: str = ""


class ReconstructionPipeline:
    """Three-tier reconstruction strategy."""

    __slots__ = ("_cache", "_checkpoints", "_seek_runtime")

    def __init__(
        self,
        *,
        seek_runtime: ReplaySeekRuntime,
        checkpoints: CheckpointRuntime,
        cache: SeekCache,
    ) -> None:
        self._seek_runtime = seek_runtime
        self._checkpoints = checkpoints
        self._cache = cache

    def reconstruct(self, target_sequence: int) -> ReconstructionOutput:
        """Rebuild state at ``target_sequence``."""
        started_ns = time.monotonic_ns()

        # ── Tier 1: cache ───────────────────────────────────────
        entry = self._cache.get(target_sequence)
        if entry is not None:
            return ReconstructionOutput(
                state=entry.state,
                landed_sequence=entry.sequence,
                landed_monotonic_ns=entry.monotonic_ns,
                used_cache=True,
                used_checkpoint=False,
                used_snapshot=False,
                frames_replayed=0,
                elapsed_ns=time.monotonic_ns() - started_ns,
            )

        # ── Tier 2: in-memory checkpoint exact hit ───────────────
        lookup: CheckpointLookup = find_nearest_checkpoint(
            self._checkpoints,
            target_sequence,
        )
        if lookup.exact_match and lookup.checkpoint is not None:
            cp = lookup.checkpoint
            return ReconstructionOutput(
                state=cp.state,
                landed_sequence=cp.sequence,
                landed_monotonic_ns=cp.monotonic_ns,
                used_cache=False,
                used_checkpoint=True,
                used_snapshot=False,
                frames_replayed=0,
                elapsed_ns=time.monotonic_ns() - started_ns,
            )

        # ── Tier 3: loader-driven reconstruction ────────────────
        try:
            outcome: SeekOutcome = self._seek_runtime.seek_to_sequence(
                target_sequence,
            )
        except Exception as exc:
            return ReconstructionOutput(
                state=VirtualRuntimeState.empty(),
                landed_sequence=0,
                landed_monotonic_ns=0,
                used_cache=False,
                used_checkpoint=False,
                used_snapshot=False,
                frames_replayed=0,
                elapsed_ns=time.monotonic_ns() - started_ns,
                error_detail=str(exc),
            )
        # Prefer the state's last_sequence — the cursor sometimes
        # reports the *start-of-reconstruction* sequence (when the
        # loader's seek landed on the snapshot anchor, not the final
        # reduced frame). The state's last_sequence reflects the
        # furthest frame the reducer actually applied.
        landed_sequence = max(
            outcome.final_state.last_sequence,
            outcome.final_cursor.last_sequence,
        )
        landed_monotonic_ns = max(
            outcome.final_state.last_monotonic_ns,
            outcome.final_cursor.last_monotonic_ns,
        )
        return ReconstructionOutput(
            state=outcome.final_state,
            landed_sequence=landed_sequence,
            landed_monotonic_ns=landed_monotonic_ns,
            used_cache=False,
            used_checkpoint=outcome.used_checkpoint,
            used_snapshot=outcome.used_snapshot,
            frames_replayed=outcome.frames_replayed,
            elapsed_ns=time.monotonic_ns() - started_ns,
        )

    def cache(
        self,
        *,
        sequence: int,
        monotonic_ns: int,
        state: VirtualRuntimeState,
    ) -> None:
        """Save a freshly-reconstructed state into the cache."""
        self._cache.put(
            SeekCacheEntry(
                sequence=sequence,
                monotonic_ns=monotonic_ns,
                state=state,
            ),
        )
