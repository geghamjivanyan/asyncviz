"""Replay session value model.

A :class:`ReplaySession` is the loader's read-only snapshot of one
recording's on-disk state. The recording layer's
:class:`RecordingMetadata` is the source of truth; this dataclass
adds the loader-side context (resolved chunk paths, snapshot paths,
detected frame format) so consumers don't have to redo path
resolution every time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from asyncviz.replay.recording.recording_metadata import (
    ChunkRecord,
    RecordingMetadata,
    SnapshotRecord,
)


@dataclass(frozen=True, slots=True)
class ReplaySession:
    """The loader's view of one recording."""

    session_dir: Path
    metadata: RecordingMetadata
    chunk_paths: tuple[Path, ...]
    snapshot_paths: tuple[Path, ...]
    detected_format: str = "auto"
    """Wire format the loader determined on first read. ``auto``
    until the first frame has been decoded."""

    @property
    def chunks(self) -> tuple[ChunkRecord, ...]:
        return self.metadata.chunks

    @property
    def snapshots(self) -> tuple[SnapshotRecord, ...]:
        return self.metadata.snapshots

    @property
    def recording_id(self) -> str:
        return self.metadata.recording_id

    @property
    def runtime_id(self) -> str:
        return self.metadata.runtime_id

    @property
    def event_count(self) -> int:
        return self.metadata.event_count

    @property
    def last_sequence(self) -> int:
        return self.metadata.last_sequence

    @property
    def finalized(self) -> bool:
        return self.metadata.finalized


@dataclass(frozen=True, slots=True)
class ReplaySessionSummary:
    """Compact summary suitable for the diagnostics page."""

    recording_id: str
    runtime_id: str
    event_count: int
    chunk_count: int
    snapshot_count: int
    last_sequence: int
    finalized: bool
    detected_format: str
    chunk_paths_missing: tuple[str, ...] = field(default_factory=tuple)
    snapshot_paths_missing: tuple[str, ...] = field(default_factory=tuple)
