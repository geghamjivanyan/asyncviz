"""Snapshot-aware state seeding.

When the engine seeks (or starts from a non-zero offset), it asks
this module to find the nearest snapshot, hydrate it into the state
store, and report the cursor anchor so the playback loop knows
where to resume.

Snapshots live in the recording layer — accessed here through the
loader's :class:`ReplaySnapshotIndex`. We keep this module thin
(one function-ish class) because the heavy lifting was already done
in the loading layer.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.loading import (
    ReplaySnapshotIndex,
    SnapshotEntry,
    load_snapshot_payload,
)
from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState
from asyncviz.replay.runtime.replay_state_store import ReplayStateStore


@dataclass(frozen=True, slots=True)
class SnapshotRestoreResult:
    """Outcome of restoring a snapshot."""

    snapshot: SnapshotEntry | None
    state: VirtualRuntimeState
    resumed_from_sequence: int
    """Sequence at which subsequent delta replay should resume."""


class SnapshotRuntime:
    """Hydrates virtual state from snapshot frames."""

    __slots__ = ("_snapshot_index", "_store")

    def __init__(
        self,
        snapshot_index: ReplaySnapshotIndex,
        state_store: ReplayStateStore,
    ) -> None:
        self._snapshot_index = snapshot_index
        self._store = state_store

    def restore_for_sequence(self, target_sequence: int) -> SnapshotRestoreResult:
        """Find + load the nearest snapshot ≤ ``target_sequence``.

        Returns a result that includes the restored state + the
        sequence the engine should resume from. If no snapshot
        exists, the state is reset to empty and the resume point is
        ``1``."""
        snapshot = self._snapshot_index.nearest_at_or_before(target_sequence)
        if snapshot is None:
            state = self._store.replace(VirtualRuntimeState.empty())
            return SnapshotRestoreResult(
                snapshot=None,
                state=state,
                resumed_from_sequence=1,
            )
        payload = load_snapshot_payload(snapshot)
        next_state = VirtualRuntimeState.from_dict(payload)
        # Anchor the state's sequence/timestamp to the snapshot.
        anchored = VirtualRuntimeState(
            last_sequence=snapshot.sequence_at_capture,
            last_monotonic_ns=next_state.last_monotonic_ns,
            frames_applied=next_state.frames_applied,
            domains=next_state.domains,
            notes=next_state.notes,
        )
        state = self._store.replace(anchored)
        return SnapshotRestoreResult(
            snapshot=snapshot,
            state=state,
            resumed_from_sequence=snapshot.sequence_at_capture + 1,
        )
