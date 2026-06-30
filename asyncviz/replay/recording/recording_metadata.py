"""Frozen metadata records that travel with a recording session.

Read from + written to the manifest file. Designed so a recording
manifest from one process version can be read by a future loader —
adding a new optional field is backwards compatible, removing or
renaming requires a ``schema_version`` bump.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    """One events-file chunk inside a session."""

    index: int
    """1-based chunk index — matches the filename digits."""

    filename: str
    event_count: int
    byte_size: int
    first_sequence: int
    last_sequence: int
    """``-1`` when no events landed in this chunk yet (the writer
    pre-allocates the file before observing events)."""

    sha256: str | None = None
    """Optional content hash. Populated at chunk finalize when
    ``RecordingConfig`` enables integrity hashes; otherwise ``None``."""


@dataclass(frozen=True, slots=True)
class SnapshotRecord:
    """One snapshot file captured during the recording."""

    index: int
    filename: str
    sequence_at_capture: int
    """The last sequence observed when this snapshot was taken — so a
    replay engine knows to apply events ``> sequence_at_capture`` on
    top of the snapshot."""

    kind: str
    """``start`` / ``rotation`` / ``checkpoint`` / ``stop`` — provenance
    for the reader."""

    byte_size: int


@dataclass(frozen=True, slots=True)
class RecordingMetadata:
    """Top-level session metadata. Persisted as ``manifest.json``."""

    schema_version: int
    recording_id: str
    runtime_id: str | None
    asyncviz_version: str
    started_at_ns: int
    stopped_at_ns: int | None
    """``None`` while the recording is in progress."""

    event_count: int
    snapshot_count: int
    chunk_count: int
    last_sequence: int
    finalized: bool
    """``True`` when ``stop()`` ran to completion. ``False`` when the
    process crashed mid-recording — the recovery layer keys off this
    bit to decide whether to truncate a partial trailing line."""

    chunks: tuple[ChunkRecord, ...] = field(default_factory=tuple)
    snapshots: tuple[SnapshotRecord, ...] = field(default_factory=tuple)
    notes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "recording_id": self.recording_id,
            "runtime_id": self.runtime_id,
            "asyncviz_version": self.asyncviz_version,
            "started_at_ns": self.started_at_ns,
            "stopped_at_ns": self.stopped_at_ns,
            "event_count": self.event_count,
            "snapshot_count": self.snapshot_count,
            "chunk_count": self.chunk_count,
            "last_sequence": self.last_sequence,
            "finalized": self.finalized,
            "chunks": [asdict(c) for c in self.chunks],
            "snapshots": [asdict(s) for s in self.snapshots],
            "notes": dict(self.notes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecordingMetadata:
        return cls(
            schema_version=int(data.get("schema_version", 0)),
            recording_id=str(data["recording_id"]),
            runtime_id=data.get("runtime_id"),
            asyncviz_version=str(data.get("asyncviz_version", "")),
            started_at_ns=int(data["started_at_ns"]),
            stopped_at_ns=(
                int(data["stopped_at_ns"]) if data.get("stopped_at_ns") is not None else None
            ),
            event_count=int(data.get("event_count", 0)),
            snapshot_count=int(data.get("snapshot_count", 0)),
            chunk_count=int(data.get("chunk_count", 0)),
            last_sequence=int(data.get("last_sequence", 0)),
            finalized=bool(data.get("finalized", False)),
            chunks=tuple(ChunkRecord(**c) for c in data.get("chunks", [])),
            snapshots=tuple(SnapshotRecord(**s) for s in data.get("snapshots", [])),
            notes=dict(data.get("notes", {})),
        )
