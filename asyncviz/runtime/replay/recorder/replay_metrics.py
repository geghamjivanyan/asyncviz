"""Process-wide recorder counters.

One singleton per process — same pattern as
:mod:`asyncviz.cli.runtime.observability`. Surfaced through the
diagnostics endpoint so operators can verify recording is healthy
without opening the bundle.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RecorderMetricsSnapshot:
    sessions_started: int
    sessions_finalized: int
    sessions_aborted: int
    events_recorded: int
    events_dropped: int
    events_filtered: int
    chunks_written: int
    bytes_written: int
    flush_count: int
    writer_errors: int
    last_session_duration_seconds: float


class _RecorderMetrics:
    def __init__(self) -> None:
        self._sessions_started = 0
        self._sessions_finalized = 0
        self._sessions_aborted = 0
        self._events_recorded = 0
        self._events_dropped = 0
        self._events_filtered = 0
        self._chunks_written = 0
        self._bytes_written = 0
        self._flush_count = 0
        self._writer_errors = 0
        self._last_duration = 0.0

    def record_session_started(self) -> None:
        self._sessions_started += 1

    def record_session_finalized(self, *, duration_seconds: float) -> None:
        self._sessions_finalized += 1
        self._last_duration = max(0.0, duration_seconds)

    def record_session_aborted(self, *, duration_seconds: float) -> None:
        self._sessions_aborted += 1
        self._last_duration = max(0.0, duration_seconds)

    def record_events(self, *, recorded: int = 0, dropped: int = 0, filtered: int = 0) -> None:
        self._events_recorded += recorded
        self._events_dropped += dropped
        self._events_filtered += filtered

    def record_chunk(self, *, bytes_written: int) -> None:
        self._chunks_written += 1
        self._bytes_written += max(0, bytes_written)

    def record_flush(self) -> None:
        self._flush_count += 1

    def record_writer_error(self) -> None:
        self._writer_errors += 1

    def snapshot(self) -> RecorderMetricsSnapshot:
        return RecorderMetricsSnapshot(
            sessions_started=self._sessions_started,
            sessions_finalized=self._sessions_finalized,
            sessions_aborted=self._sessions_aborted,
            events_recorded=self._events_recorded,
            events_dropped=self._events_dropped,
            events_filtered=self._events_filtered,
            chunks_written=self._chunks_written,
            bytes_written=self._bytes_written,
            flush_count=self._flush_count,
            writer_errors=self._writer_errors,
            last_session_duration_seconds=self._last_duration,
        )

    def reset(self) -> None:
        self.__init__()


_instance = _RecorderMetrics()


def get_recorder_metrics() -> _RecorderMetrics:
    return _instance


def reset_recorder_metrics() -> None:
    _instance.reset()
