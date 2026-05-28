"""Recovery wrappers for the loader's chunk-iteration paths.

The recording layer already provides :mod:`recording_integrity`
helpers (``repair_partial_tail``, ``count_chunk_events``,
``compute_chunk_hash``). The loader doesn't *write* — so we don't
truncate corrupt files here. Instead we:

* Detect chunks that look damaged (size mismatch, hash mismatch, no
  valid trailing newline) and report them via :class:`ChunkHealth`.
* Provide a streaming :class:`RecoveringChunkLoader` that yields the
  frames it can recover from a chunk that holds malformed lines.

Repair-on-disk is intentionally out of scope here — the loader is
*read-only* by design, so production recordings don't get
unintentionally mutated during inspection.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.format.ndjson_streaming import iter_lines
from asyncviz.replay.loading.models.frame_adapter import (
    FrameAdapter,
    FrameAdapterError,
)
from asyncviz.replay.loading.replay_observability import get_loader_metrics
from asyncviz.replay.loading.replay_tracing import record_replay_trace
from asyncviz.replay.recording.recording_integrity import count_chunk_events
from asyncviz.replay.recording.recording_metadata import ChunkRecord


@dataclass(frozen=True, slots=True)
class ChunkHealth:
    """Health assessment for one chunk without modifying it."""

    chunk_index: int
    path: Path
    byte_size: int
    line_count: int
    expected_event_count: int
    has_trailing_newline: bool
    """If False, the last byte is something other than ``\\n`` —
    a strong hint a writer crashed mid-line."""

    healthy: bool


def inspect_chunk(chunk: ChunkRecord, path: Path) -> ChunkHealth:
    """Cheap on-disk health check."""
    if not path.exists():
        return ChunkHealth(
            chunk_index=chunk.index,
            path=path,
            byte_size=0,
            line_count=0,
            expected_event_count=chunk.event_count,
            has_trailing_newline=True,
            healthy=False,
        )
    size = path.stat().st_size
    line_count = count_chunk_events(path)
    has_newline = True
    if size > 0:
        with path.open("rb") as fh:
            fh.seek(-1, 2)
            has_newline = fh.read(1) == b"\n"
    healthy = (
        size > 0
        and has_newline
        and (chunk.event_count == 0 or line_count >= chunk.event_count)
    )
    return ChunkHealth(
        chunk_index=chunk.index,
        path=path,
        byte_size=size,
        line_count=line_count,
        expected_event_count=chunk.event_count,
        has_trailing_newline=has_newline,
        healthy=healthy,
    )


class RecoveringChunkLoader:
    """Yields every frame a chunk can produce; counts what it had to
    drop. Distinct from :class:`ReplayChunkLoader` only in that the
    *intent* here is explicit recovery — the metric labels are
    different and trace events use ``recovery-applied``."""

    __slots__ = ("_adapter", "_chunk", "_dropped", "_path", "_recovered")

    def __init__(
        self, chunk: ChunkRecord, path: Path, *, adapter: FrameAdapter,
    ) -> None:
        self._chunk = chunk
        self._path = path
        self._adapter = adapter
        self._recovered = 0
        self._dropped = 0

    @property
    def recovered(self) -> int:
        return self._recovered

    @property
    def dropped(self) -> int:
        return self._dropped

    def __iter__(self) -> Iterator[ReplayFrame]:
        if not self._path.exists():
            return
        for line in iter_lines(self._path):
            try:
                frame = self._adapter.decode_line(line)
            except FrameAdapterError:
                self._dropped += 1
                get_loader_metrics().record_malformed_frame()
                continue
            self._recovered += 1
            yield frame
        record_replay_trace(
            "recovery-applied",
            f"chunk={self._chunk.index} recovered={self._recovered} dropped={self._dropped}",
        )
