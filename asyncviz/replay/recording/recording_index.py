"""Sequence → chunk index for fast replay seeking.

The index is computed at finalize time (cheap — one pass over the
on-disk chunks) and persisted as ``index.json`` alongside the
manifest. Replay seeking by sequence becomes a single dict lookup +
linear chunk read rather than a full-log scan.

For sessions that crashed before finalize, the index can be rebuilt
from the recovered chunks via :func:`build_index_from_chunks`.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from asyncviz.replay.recording.recording_layout import (
    events_chunk_path,
    index_path,
)
from asyncviz.replay.recording.recording_metadata import ChunkRecord
from asyncviz.replay.recording.recording_paths import atomic_replace


@dataclass(frozen=True, slots=True)
class IndexEntry:
    chunk_index: int
    first_sequence: int
    last_sequence: int
    """``-1`` for empty chunks."""

    event_count: int


@dataclass(frozen=True, slots=True)
class RecordingIndex:
    entries: tuple[IndexEntry, ...]

    def chunk_for_sequence(self, sequence: int) -> IndexEntry | None:
        """Return the chunk containing ``sequence``, or ``None`` when
        the sequence falls outside every chunk."""
        for entry in self.entries:
            if entry.first_sequence < 0:
                continue
            if entry.first_sequence <= sequence <= entry.last_sequence:
                return entry
        return None

    def to_dict(self) -> dict:
        return {"entries": [asdict(e) for e in self.entries]}

    @classmethod
    def from_dict(cls, data: dict) -> RecordingIndex:
        entries = tuple(
            IndexEntry(
                chunk_index=int(e["chunk_index"]),
                first_sequence=int(e["first_sequence"]),
                last_sequence=int(e["last_sequence"]),
                event_count=int(e["event_count"]),
            )
            for e in data.get("entries", [])
        )
        return cls(entries=entries)


def build_index_from_chunks(chunks: list[ChunkRecord]) -> RecordingIndex:
    entries: list[IndexEntry] = []
    for chunk in chunks:
        entries.append(
            IndexEntry(
                chunk_index=chunk.index,
                first_sequence=chunk.first_sequence,
                last_sequence=chunk.last_sequence,
                event_count=chunk.event_count,
            ),
        )
    entries.sort(key=lambda e: e.chunk_index)
    return RecordingIndex(entries=tuple(entries))


def write_index(session_dir: Path, index: RecordingIndex) -> Path:
    target = index_path(session_dir)
    serialized = json.dumps(index.to_dict(), indent=2, sort_keys=True) + "\n"
    import tempfile

    fd, tmp_path_str = tempfile.mkstemp(
        prefix=".index.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    tmp_path = Path(tmp_path_str)
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(serialized)
            f.flush()
        atomic_replace(tmp_path, target)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return target


def read_index(session_dir: Path) -> RecordingIndex | None:
    target = index_path(session_dir)
    if not target.exists():
        return None
    return RecordingIndex.from_dict(json.loads(target.read_text(encoding="utf-8")))


def chunk_path_for_entry(session_dir: Path, entry: IndexEntry) -> Path:
    return events_chunk_path(session_dir, entry.chunk_index)
