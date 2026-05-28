"""Small navigation helpers used by multiple loader pieces."""

from __future__ import annotations

from pathlib import Path

from asyncviz.replay.format.ndjson_streaming import iter_lines
from asyncviz.replay.loading.models.frame_adapter import (
    AutoDetectFrameAdapter,
    CanonicalFrameAdapter,
    FrameAdapter,
    LegacyRecordingFrameAdapter,
)
from asyncviz.replay.recording.recording_metadata import ChunkRecord


def detect_format_from_session(chunk_paths: tuple[Path, ...]) -> FrameAdapter:
    """Sniff the first non-empty line of the first chunk and return
    the matching adapter. Falls back to the auto-detect adapter
    (which performs the same sniff lazily) if no chunk has any
    content."""
    for path in chunk_paths:
        if not path.exists():
            continue
        for line in iter_lines(path):
            if not line.strip():
                continue
            sniffer = AutoDetectFrameAdapter()
            try:
                sniffer.decode_line(line)
            except Exception:
                return LegacyRecordingFrameAdapter()
            inner = sniffer.selected
            return inner if inner is not None else CanonicalFrameAdapter()
    return AutoDetectFrameAdapter()


def pick_starting_chunk(
    chunks: tuple[ChunkRecord, ...], sequence: int,
) -> ChunkRecord | None:
    """Linear-scan helper used by the seek planner for tiny chunk
    inventories where bisect's overhead isn't worth it."""
    for chunk in chunks:
        if chunk.first_sequence <= sequence <= chunk.last_sequence:
            return chunk
    return None
