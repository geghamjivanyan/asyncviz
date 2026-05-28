"""Per-session statistics for the replay recorder."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class RecordingStatistics:
    """Cumulative counters for one recording session.

    Snapshots are written into the bundle's ``meta/recorder.json`` so
    operators can audit the recorder without rummaging through
    chunks.
    """

    started_at_monotonic: float = field(default_factory=time.monotonic)
    finished_at_monotonic: float | None = None
    events_seen: int = 0
    events_recorded: int = 0
    events_filtered: int = 0
    events_dropped: int = 0
    chunks_written: int = 0
    bytes_serialized: int = 0
    bytes_on_disk: int = 0
    flushes: int = 0
    writer_errors: int = 0
    first_sequence: int | None = None
    last_sequence: int | None = None
    finalized_cleanly: bool = False

    def record_event_seen(self) -> None:
        self.events_seen += 1

    def record_event_recorded(self, *, sequence: int, payload_size: int) -> None:
        self.events_recorded += 1
        self.bytes_serialized += payload_size
        if self.first_sequence is None or sequence < self.first_sequence:
            self.first_sequence = sequence
        if self.last_sequence is None or sequence > self.last_sequence:
            self.last_sequence = sequence

    def record_event_filtered(self) -> None:
        self.events_filtered += 1

    def record_event_dropped(self) -> None:
        self.events_dropped += 1

    def record_chunk_finalized(self, *, bytes_on_disk: int) -> None:
        self.chunks_written += 1
        self.bytes_on_disk += bytes_on_disk

    def record_flush(self) -> None:
        self.flushes += 1

    def record_writer_error(self) -> None:
        self.writer_errors += 1

    def mark_finished(self, *, cleanly: bool) -> None:
        self.finished_at_monotonic = time.monotonic()
        self.finalized_cleanly = cleanly

    @property
    def duration_seconds(self) -> float:
        end = self.finished_at_monotonic or time.monotonic()
        return max(0.0, end - self.started_at_monotonic)

    def to_dict(self) -> dict[str, object]:
        return {
            "started_at_monotonic": self.started_at_monotonic,
            "finished_at_monotonic": self.finished_at_monotonic,
            "duration_seconds": self.duration_seconds,
            "events_seen": self.events_seen,
            "events_recorded": self.events_recorded,
            "events_filtered": self.events_filtered,
            "events_dropped": self.events_dropped,
            "chunks_written": self.chunks_written,
            "bytes_serialized": self.bytes_serialized,
            "bytes_on_disk": self.bytes_on_disk,
            "flushes": self.flushes,
            "writer_errors": self.writer_errors,
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
            "finalized_cleanly": self.finalized_cleanly,
        }
