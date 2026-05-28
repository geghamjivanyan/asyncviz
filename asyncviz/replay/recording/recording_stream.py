"""Read-side iterator over a finalized recording.

Discovers chunks via the manifest (preferred) or by scanning the
``events/`` directory (fallback for crashed sessions whose manifest
hasn't been fully recovered yet). Yields events in sequence order.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from asyncviz.replay.recording.recording_layout import (
    events_chunk_path,
    events_dir,
)
from asyncviz.replay.recording.recording_manifest import read_manifest
from asyncviz.replay.recording.recording_writer import iter_chunk_lines


@dataclass(frozen=True, slots=True)
class RecordedFrame:
    """One reconstructed event frame from disk."""

    sequence: int
    event_id: str
    event_type: str
    monotonic_ns: int
    payload: dict[str, Any]


class RecordingStream:
    """Iterator surface over a recording session's events.

    Construct with the session directory; iterate to receive
    :class:`RecordedFrame` objects in sequence order. Skips malformed
    lines defensively.
    """

    def __init__(self, session_dir: Path) -> None:
        self._session_dir = session_dir

    def __iter__(self) -> Iterator[RecordedFrame]:
        for chunk_path in self._iter_chunk_paths():
            for line in iter_chunk_lines(chunk_path):
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                yield RecordedFrame(
                    sequence=int(data.get("sequence", 0)),
                    event_id=str(data.get("event_id", "")),
                    event_type=str(data.get("event_type", "")),
                    monotonic_ns=int(data.get("monotonic_ns", 0) or 0),
                    payload=dict(data.get("payload", {})),
                )

    def events_after(self, sequence: int) -> Iterator[RecordedFrame]:
        """Yield events with ``frame.sequence > sequence``."""
        for frame in self:
            if frame.sequence > sequence:
                yield frame

    def events_in_range(
        self, *, start_sequence: int, end_sequence: int,
    ) -> Iterator[RecordedFrame]:
        for frame in self:
            if frame.sequence < start_sequence:
                continue
            if frame.sequence > end_sequence:
                return
            yield frame

    def count_events(self) -> int:
        return sum(1 for _ in self)

    def _iter_chunk_paths(self) -> Iterator[Path]:
        metadata = None
        try:
            metadata = read_manifest(self._session_dir)
        except ValueError:
            metadata = None  # malformed manifest → fall back to scan
        if metadata is not None and metadata.chunks:
            for chunk in sorted(metadata.chunks, key=lambda c: c.index):
                yield events_chunk_path(self._session_dir, chunk.index)
            return
        events_path = events_dir(self._session_dir)
        if events_path.exists():
            yield from sorted(events_path.glob("*.ndjson"))
