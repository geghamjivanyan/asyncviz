"""Replay-format observability counters.

Every encode/decode/validation step funnels through a few atomic
counters so the diagnostics page can show format health without
needing to walk an entire recording. Counts are process-wide and
thread-safe; tests reset them via :func:`reset_format_metrics`.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NdjsonFormatMetricsSnapshot:
    """Immutable view of the format metrics — diagnostics payload."""

    frames_encoded: int = 0
    frames_decoded: int = 0
    bytes_encoded: int = 0
    bytes_decoded: int = 0
    malformed_frames: int = 0
    validation_failures: int = 0
    sequence_violations: int = 0
    duplicate_sequences: int = 0
    integrity_failures: int = 0
    migrations_applied: int = 0
    schema_skews_observed: int = 0
    backpressure_events: int = 0
    decoder_recursions_skipped: int = 0


class _FormatMetrics:
    """Process-wide mutable counters behind a single lock."""

    __slots__ = (
        "_backpressure_events",
        "_bytes_decoded",
        "_bytes_encoded",
        "_decoder_recursions_skipped",
        "_duplicate_sequences",
        "_frames_decoded",
        "_frames_encoded",
        "_integrity_failures",
        "_lock",
        "_malformed_frames",
        "_migrations_applied",
        "_schema_skews_observed",
        "_sequence_violations",
        "_validation_failures",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reset_locked()

    def _reset_locked(self) -> None:
        self._frames_encoded = 0
        self._frames_decoded = 0
        self._bytes_encoded = 0
        self._bytes_decoded = 0
        self._malformed_frames = 0
        self._validation_failures = 0
        self._sequence_violations = 0
        self._duplicate_sequences = 0
        self._integrity_failures = 0
        self._migrations_applied = 0
        self._schema_skews_observed = 0
        self._backpressure_events = 0
        self._decoder_recursions_skipped = 0

    # ── public mutators ───────────────────────────────────────────

    def record_frame_encoded(self, bytes_written: int) -> None:
        with self._lock:
            self._frames_encoded += 1
            self._bytes_encoded += bytes_written

    def record_frame_decoded(self, bytes_read: int) -> None:
        with self._lock:
            self._frames_decoded += 1
            self._bytes_decoded += bytes_read

    def record_malformed_frame(self) -> None:
        with self._lock:
            self._malformed_frames += 1

    def record_validation_failure(self) -> None:
        with self._lock:
            self._validation_failures += 1

    def record_sequence_violation(self) -> None:
        with self._lock:
            self._sequence_violations += 1

    def record_duplicate_sequence(self) -> None:
        with self._lock:
            self._duplicate_sequences += 1

    def record_integrity_failure(self) -> None:
        with self._lock:
            self._integrity_failures += 1

    def record_migration_applied(self) -> None:
        with self._lock:
            self._migrations_applied += 1

    def record_schema_skew(self) -> None:
        with self._lock:
            self._schema_skews_observed += 1

    def record_backpressure_event(self) -> None:
        with self._lock:
            self._backpressure_events += 1

    def record_decoder_recursion_skip(self) -> None:
        with self._lock:
            self._decoder_recursions_skipped += 1

    def snapshot(self) -> NdjsonFormatMetricsSnapshot:
        with self._lock:
            return NdjsonFormatMetricsSnapshot(
                frames_encoded=self._frames_encoded,
                frames_decoded=self._frames_decoded,
                bytes_encoded=self._bytes_encoded,
                bytes_decoded=self._bytes_decoded,
                malformed_frames=self._malformed_frames,
                validation_failures=self._validation_failures,
                sequence_violations=self._sequence_violations,
                duplicate_sequences=self._duplicate_sequences,
                integrity_failures=self._integrity_failures,
                migrations_applied=self._migrations_applied,
                schema_skews_observed=self._schema_skews_observed,
                backpressure_events=self._backpressure_events,
                decoder_recursions_skipped=self._decoder_recursions_skipped,
            )

    def reset(self) -> None:
        with self._lock:
            self._reset_locked()


_METRICS: _FormatMetrics | None = None
_METRICS_LOCK = threading.Lock()


def get_format_metrics() -> _FormatMetrics:
    global _METRICS
    if _METRICS is None:
        with _METRICS_LOCK:
            if _METRICS is None:
                _METRICS = _FormatMetrics()
    return _METRICS


def get_format_metrics_snapshot() -> NdjsonFormatMetricsSnapshot:
    return get_format_metrics().snapshot()


def reset_format_metrics() -> None:
    if _METRICS is not None:
        _METRICS.reset()
