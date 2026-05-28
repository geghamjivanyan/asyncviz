"""Sequence → chunk lookup for the replay loader.

The recording layer already produces :class:`RecordingIndex` when
the writer is configured with ``enable_index=True``. The loader-side
wrapper:

* Loads that index if present.
* Falls back to building one in memory from the manifest's chunk
  records (which always carry ``first_sequence`` /
  ``last_sequence``).
* Adds binary search over chunk records for ``chunk_for_sequence``
  so seeks are O(log n) instead of O(n) over chunk count.

The wrapper is *value-only* — no IO after construction — so it's
cheap to pass around between cursors and seek operations.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

from asyncviz.replay.recording.recording_index import (
    IndexEntry,
    build_index_from_chunks,
    read_index as _read_recording_index,
)
from asyncviz.replay.recording.recording_metadata import ChunkRecord, RecordingMetadata


@dataclass(frozen=True, slots=True)
class ReplayIndex:
    """Immutable seq → chunk lookup."""

    entries: tuple[IndexEntry, ...]
    _starts: tuple[int, ...]
    """``first_sequence`` of each entry, in order. Used by
    :meth:`chunk_for_sequence` for the binary search."""

    @staticmethod
    def from_metadata(metadata: RecordingMetadata) -> ReplayIndex:
        """Build an index purely from the manifest's chunk records."""
        index = build_index_from_chunks(metadata.chunks)
        entries = tuple(sorted(index.entries, key=lambda e: e.first_sequence))
        starts = tuple(e.first_sequence for e in entries)
        return ReplayIndex(entries=entries, _starts=starts)

    @staticmethod
    def from_session_dir(session_dir: Path, metadata: RecordingMetadata) -> ReplayIndex:
        """Prefer the on-disk index file; fall back to the manifest."""
        on_disk = _read_recording_index(session_dir)
        if on_disk is None:
            return ReplayIndex.from_metadata(metadata)
        entries = tuple(sorted(on_disk.entries, key=lambda e: e.first_sequence))
        starts = tuple(e.first_sequence for e in entries)
        return ReplayIndex(entries=entries, _starts=starts)

    def chunk_for_sequence(self, sequence: int) -> IndexEntry | None:
        """Return the index entry whose sequence range contains
        ``sequence`` (inclusive), or ``None`` if no entry matches."""
        if not self.entries:
            return None
        # Binary search by first_sequence: bisect_right(starts, seq)
        # gives us the first entry strictly after; the chunk
        # containing ``sequence`` is the one before that.
        pos = bisect_right(self._starts, sequence) - 1
        if pos < 0:
            return None
        candidate = self.entries[pos]
        if sequence > candidate.last_sequence:
            return None
        return candidate

    def chunk_record_for_sequence(
        self, sequence: int, chunks: tuple[ChunkRecord, ...],
    ) -> ChunkRecord | None:
        entry = self.chunk_for_sequence(sequence)
        if entry is None:
            return None
        return next((c for c in chunks if c.index == entry.chunk_index), None)

    @property
    def chunk_count(self) -> int:
        return len(self.entries)

    @property
    def event_count(self) -> int:
        return sum(e.event_count for e in self.entries)

    @property
    def min_sequence(self) -> int:
        return self.entries[0].first_sequence if self.entries else 0

    @property
    def max_sequence(self) -> int:
        return self.entries[-1].last_sequence if self.entries else 0
