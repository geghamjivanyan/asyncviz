"""Per-chunk loader — iterate one event chunk lazily.

Wraps a single ``.ndjson`` chunk file behind a small contract:

* :meth:`iter_frames` opens the file, walks it line-by-line through
  the configured :class:`FrameAdapter`, and yields valid frames.
* Malformed lines are *isolated* — counted, traced, and skipped —
  unless ``strict=True`` is set on the loader, in which case the
  first failure propagates.

This module deliberately knows nothing about the manifest or the
session — it operates on the ``(chunk_record, path)`` pair the
session loader hands it. That keeps it useful for ad-hoc replay
tooling that wants to walk one chunk without opening a full session.
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
from asyncviz.replay.recording.recording_metadata import ChunkRecord


@dataclass(frozen=True, slots=True)
class ChunkReadReport:
    """Outcome of one chunk-iteration pass."""

    chunk_index: int
    lines_read: int
    frames_yielded: int
    lines_dropped: int


class ReplayChunkLoader:
    """Lazy iterator over the frames inside one chunk file."""

    __slots__ = ("_adapter", "_chunk", "_path", "_strict")

    def __init__(
        self,
        chunk: ChunkRecord,
        path: Path,
        *,
        adapter: FrameAdapter,
        strict: bool = False,
    ) -> None:
        self._chunk = chunk
        self._path = path
        self._adapter = adapter
        self._strict = strict

    @property
    def chunk(self) -> ChunkRecord:
        return self._chunk

    @property
    def path(self) -> Path:
        return self._path

    @property
    def exists(self) -> bool:
        return self._path.exists()

    def iter_frames(self) -> Iterator[ReplayFrame]:
        """Walk the chunk and yield decoded frames."""
        if not self._path.exists():
            get_loader_metrics().record_chunk_skipped()
            record_replay_trace("chunk-skipped", f"index={self._chunk.index} missing")
            return
        get_loader_metrics().record_chunk_scanned()
        record_replay_trace("chunk-opened", f"index={self._chunk.index}")
        try:
            for line in iter_lines(self._path):
                try:
                    frame = self._adapter.decode_line(line)
                except FrameAdapterError:
                    get_loader_metrics().record_malformed_frame()
                    record_replay_trace(
                        "frame-dropped",
                        f"index={self._chunk.index}",
                    )
                    if self._strict:
                        raise
                    continue
                yield frame
        finally:
            record_replay_trace("chunk-closed", f"index={self._chunk.index}")

    def read_report(self) -> ChunkReadReport:
        """Convenience: materialize the chunk + count the outcome.
        Use sparingly (allocates a full list)."""
        frames: list[ReplayFrame] = []
        lines = 0
        dropped = 0
        if not self._path.exists():
            return ChunkReadReport(self._chunk.index, 0, 0, 0)
        for line in iter_lines(self._path):
            lines += 1
            try:
                frames.append(self._adapter.decode_line(line))
            except FrameAdapterError:
                dropped += 1
        return ChunkReadReport(
            chunk_index=self._chunk.index,
            lines_read=lines,
            frames_yielded=len(frames),
            lines_dropped=dropped,
        )
