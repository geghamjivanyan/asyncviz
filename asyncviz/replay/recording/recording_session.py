"""Session lifecycle state machine.

A :class:`RecordingSession` is the in-memory bookkeeping for one
recording. It tracks counters + lifecycle state + metadata that
eventually lands in the manifest.

The state machine is intentionally tiny:

    idle ──▶ recording ──▶ stopping ──▶ stopped
                                       ╲
                                        ╲─▶ failed
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

SessionState = Literal["idle", "recording", "stopping", "stopped", "failed"]


@dataclass
class RecordingSession:
    """Mutable session bookkeeping. Thread-safe — every counter bump
    goes through an internal lock so the writer worker + the recorder
    facade can update it concurrently."""

    recording_id: str
    runtime_id: str | None
    asyncviz_version: str
    state: SessionState = "idle"
    started_at_ns: int = 0
    stopped_at_ns: int | None = None
    event_count: int = 0
    snapshot_count: int = 0
    chunk_count: int = 0
    last_sequence: int = 0
    notes: dict = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def new(
        cls,
        *,
        runtime_id: str | None,
        asyncviz_version: str,
        recording_id: str | None = None,
    ) -> RecordingSession:
        return cls(
            recording_id=recording_id or str(uuid.uuid4()),
            runtime_id=runtime_id,
            asyncviz_version=asyncviz_version,
        )

    def mark_started(self) -> None:
        with self._lock:
            self.state = "recording"
            self.started_at_ns = time.monotonic_ns()

    def mark_stopping(self) -> None:
        with self._lock:
            if self.state == "recording":
                self.state = "stopping"

    def mark_stopped(self) -> None:
        with self._lock:
            self.state = "stopped"
            self.stopped_at_ns = time.monotonic_ns()

    def mark_failed(self, *, reason: str | None = None) -> None:
        with self._lock:
            self.state = "failed"
            self.stopped_at_ns = time.monotonic_ns()
            if reason:
                self.notes["failure_reason"] = reason

    def record_event(self, sequence: int) -> None:
        with self._lock:
            self.event_count += 1
            if sequence > self.last_sequence:
                self.last_sequence = sequence

    def record_snapshot(self) -> None:
        with self._lock:
            self.snapshot_count += 1

    def record_chunk_rotation(self) -> None:
        with self._lock:
            self.chunk_count += 1

    @property
    def is_finalized(self) -> bool:
        return self.state in ("stopped", "failed")
