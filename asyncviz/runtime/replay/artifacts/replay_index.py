"""Sequence index for a replay bundle.

Useful for replay viewers that want to jump to a specific sequence
without scanning every chunk. The index is built on demand from the
manifest (which already carries ``sequence_start`` /
``sequence_end`` per chunk).
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from asyncviz.runtime.replay.recorder.replay_manifest import (
    ChunkManifestEntry,
    ReplayBundleManifest,
)


@dataclass(frozen=True, slots=True)
class ReplayChunkIndexEntry:
    chunk: ChunkManifestEntry
    chunk_index: int


class ReplayEventIndex:
    """Sequence-range index over the manifest's chunks."""

    def __init__(self, entries: tuple[ReplayChunkIndexEntry, ...]) -> None:
        self._entries = entries
        # Precompute the starts vector for binary search.
        self._starts = tuple(entry.chunk.sequence_start for entry in entries)

    @property
    def entries(self) -> tuple[ReplayChunkIndexEntry, ...]:
        return self._entries

    def chunk_for(self, sequence: int) -> ReplayChunkIndexEntry | None:
        if not self._entries:
            return None
        idx = bisect_right(self._starts, sequence) - 1
        if idx < 0:
            return None
        entry = self._entries[idx]
        if sequence > entry.chunk.sequence_end:
            return None
        return entry


def build_index(manifest: ReplayBundleManifest) -> ReplayEventIndex:
    entries = tuple(
        ReplayChunkIndexEntry(chunk=chunk, chunk_index=i)
        for i, chunk in enumerate(manifest.chunks)
    )
    return ReplayEventIndex(entries)
