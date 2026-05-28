"""Engine-level observability counters for the runtime recorder."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RecordingMetricsSnapshot:
    sessions_started: int
    sessions_stopped: int
    events_persisted: int
    events_dropped: int
    bytes_written: int
    flushes_completed: int
    flush_failures: int
    rotations: int
    snapshots_captured: int
    repairs_completed: int
    integrity_failures: int
    queue_depth: int
    recursion_skips: int


class _RecordingMetrics:
    __slots__ = (
        "_bytes_written",
        "_events_dropped",
        "_events_persisted",
        "_flush_failures",
        "_flushes_completed",
        "_integrity_failures",
        "_lock",
        "_queue_depth",
        "_recursion_skips",
        "_repairs_completed",
        "_rotations",
        "_sessions_started",
        "_sessions_stopped",
        "_snapshots_captured",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions_started = 0
        self._sessions_stopped = 0
        self._events_persisted = 0
        self._events_dropped = 0
        self._bytes_written = 0
        self._flushes_completed = 0
        self._flush_failures = 0
        self._rotations = 0
        self._snapshots_captured = 0
        self._repairs_completed = 0
        self._integrity_failures = 0
        self._queue_depth = 0
        self._recursion_skips = 0

    def record_session_started(self) -> None:
        with self._lock:
            self._sessions_started += 1

    def record_session_stopped(self) -> None:
        with self._lock:
            self._sessions_stopped += 1

    def record_event_persisted(self, byte_size: int) -> None:
        with self._lock:
            self._events_persisted += 1
            self._bytes_written += byte_size

    def record_event_dropped(self) -> None:
        with self._lock:
            self._events_dropped += 1

    def record_flush_completed(self) -> None:
        with self._lock:
            self._flushes_completed += 1

    def record_flush_failure(self) -> None:
        with self._lock:
            self._flush_failures += 1

    def record_rotation(self) -> None:
        with self._lock:
            self._rotations += 1

    def record_snapshot_captured(self) -> None:
        with self._lock:
            self._snapshots_captured += 1

    def record_repair_completed(self) -> None:
        with self._lock:
            self._repairs_completed += 1

    def record_integrity_failure(self) -> None:
        with self._lock:
            self._integrity_failures += 1

    def record_recursion_skip(self) -> None:
        with self._lock:
            self._recursion_skips += 1

    def set_queue_depth(self, depth: int) -> None:
        with self._lock:
            self._queue_depth = depth

    def snapshot(self) -> RecordingMetricsSnapshot:
        with self._lock:
            return RecordingMetricsSnapshot(
                sessions_started=self._sessions_started,
                sessions_stopped=self._sessions_stopped,
                events_persisted=self._events_persisted,
                events_dropped=self._events_dropped,
                bytes_written=self._bytes_written,
                flushes_completed=self._flushes_completed,
                flush_failures=self._flush_failures,
                rotations=self._rotations,
                snapshots_captured=self._snapshots_captured,
                repairs_completed=self._repairs_completed,
                integrity_failures=self._integrity_failures,
                queue_depth=self._queue_depth,
                recursion_skips=self._recursion_skips,
            )

    def reset(self) -> None:
        with self._lock:
            self._sessions_started = 0
            self._sessions_stopped = 0
            self._events_persisted = 0
            self._events_dropped = 0
            self._bytes_written = 0
            self._flushes_completed = 0
            self._flush_failures = 0
            self._rotations = 0
            self._snapshots_captured = 0
            self._repairs_completed = 0
            self._integrity_failures = 0
            self._queue_depth = 0
            self._recursion_skips = 0


_default_metrics = _RecordingMetrics()


def get_recording_metrics() -> _RecordingMetrics:
    return _default_metrics


def reset_recording_metrics() -> None:
    _default_metrics.reset()
