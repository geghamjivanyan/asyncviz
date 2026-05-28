"""Snapshot index — find the nearest snapshot ≤ a given sequence.

Snapshots are full-state checkpoints. The replay engine uses them to
seek without replaying from sequence zero: pick the snapshot whose
``sequence_at_capture`` is the largest value ≤ the seek target, load
its bytes, then replay deltas from there forward.

This module produces a sorted index over the manifest's snapshot
records + the resolved on-disk paths, plus a small JSON loader for
the snapshot payloads themselves.
"""

from __future__ import annotations

import json
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from asyncviz.replay.loading.replay_observability import get_loader_metrics
from asyncviz.replay.loading.replay_tracing import record_replay_trace
from asyncviz.replay.recording.recording_metadata import SnapshotRecord


@dataclass(frozen=True, slots=True)
class SnapshotEntry:
    """One snapshot in the index — record + resolved path."""

    record: SnapshotRecord
    path: Path
    sequence_at_capture: int


@dataclass(frozen=True, slots=True)
class ReplaySnapshotIndex:
    """Sorted-by-``sequence_at_capture`` snapshot lookup."""

    entries: tuple[SnapshotEntry, ...]
    _captures: tuple[int, ...]
    """``sequence_at_capture`` of each entry, in order."""

    @staticmethod
    def from_records(
        snapshots: tuple[SnapshotRecord, ...], snapshot_paths: tuple[Path, ...],
    ) -> ReplaySnapshotIndex:
        if len(snapshots) != len(snapshot_paths):
            raise ValueError(
                f"snapshot records ({len(snapshots)}) and paths "
                f"({len(snapshot_paths)}) must match in length",
            )
        entries = tuple(
            sorted(
                (
                    SnapshotEntry(
                        record=record,
                        path=path,
                        sequence_at_capture=record.sequence_at_capture,
                    )
                    for record, path in zip(snapshots, snapshot_paths, strict=True)
                ),
                key=lambda e: e.sequence_at_capture,
            ),
        )
        captures = tuple(e.sequence_at_capture for e in entries)
        return ReplaySnapshotIndex(entries=entries, _captures=captures)

    def nearest_at_or_before(self, sequence: int) -> SnapshotEntry | None:
        """Return the snapshot with the highest ``sequence_at_capture``
        that is still ``<= sequence``, or ``None`` if no snapshot
        was taken at or before ``sequence``."""
        if not self.entries:
            return None
        pos = bisect_right(self._captures, sequence) - 1
        if pos < 0:
            return None
        return self.entries[pos]

    @property
    def snapshot_count(self) -> int:
        return len(self.entries)


def load_snapshot_payload(entry: SnapshotEntry) -> dict[str, Any]:
    """Read + parse one snapshot file. Raises ``ValueError`` on
    malformed JSON; bumps the loader metrics on success."""
    if not entry.path.exists():
        raise FileNotFoundError(f"snapshot file missing: {entry.path}")
    text = entry.path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed snapshot at {entry.path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(
            f"snapshot payload must be a JSON object (got {type(data).__name__})",
        )
    get_loader_metrics().record_snapshot_loaded()
    record_replay_trace(
        "snapshot-loaded",
        f"index={entry.record.index} seq={entry.sequence_at_capture}",
    )
    return data
