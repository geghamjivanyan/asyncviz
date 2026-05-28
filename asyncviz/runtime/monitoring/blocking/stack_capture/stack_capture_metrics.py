"""Lifetime counters for the stack-capture engine."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StackCaptureMetricsSnapshot:
    """Immutable view of the engine's lifetime self-metrics."""

    outcomes_observed: int
    captures_attempted: int
    captures_emitted: int
    captures_dropped_backpressure: int
    captures_dropped_emitter: int
    captures_skipped_policy: int
    captures_skipped_reentry: int
    sampler_failures: int
    serializer_failures: int
    emitter_failures: int
    payload_trims: int
    total_payload_bytes: int
    max_payload_bytes_observed: int
    total_frames_emitted: int
    total_frames_filtered: int
    reconfigurations: int
    handler_failures: int

    def to_dict(self) -> dict[str, int]:
        return {
            "outcomes_observed": self.outcomes_observed,
            "captures_attempted": self.captures_attempted,
            "captures_emitted": self.captures_emitted,
            "captures_dropped_backpressure": self.captures_dropped_backpressure,
            "captures_dropped_emitter": self.captures_dropped_emitter,
            "captures_skipped_policy": self.captures_skipped_policy,
            "captures_skipped_reentry": self.captures_skipped_reentry,
            "sampler_failures": self.sampler_failures,
            "serializer_failures": self.serializer_failures,
            "emitter_failures": self.emitter_failures,
            "payload_trims": self.payload_trims,
            "total_payload_bytes": self.total_payload_bytes,
            "max_payload_bytes_observed": self.max_payload_bytes_observed,
            "total_frames_emitted": self.total_frames_emitted,
            "total_frames_filtered": self.total_frames_filtered,
            "reconfigurations": self.reconfigurations,
            "handler_failures": self.handler_failures,
        }


class StackCaptureMetrics:
    """Mutable counters. Thread-safe via single lock; updates are O(1)."""

    __slots__ = (
        "_captures_attempted",
        "_captures_dropped_backpressure",
        "_captures_dropped_emitter",
        "_captures_emitted",
        "_captures_skipped_policy",
        "_captures_skipped_reentry",
        "_emitter_failures",
        "_handler_failures",
        "_lock",
        "_max_payload_bytes",
        "_outcomes_observed",
        "_payload_trims",
        "_reconfigurations",
        "_sampler_failures",
        "_serializer_failures",
        "_total_frames_emitted",
        "_total_frames_filtered",
        "_total_payload_bytes",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._outcomes_observed = 0
        self._captures_attempted = 0
        self._captures_emitted = 0
        self._captures_dropped_backpressure = 0
        self._captures_dropped_emitter = 0
        self._captures_skipped_policy = 0
        self._captures_skipped_reentry = 0
        self._sampler_failures = 0
        self._serializer_failures = 0
        self._emitter_failures = 0
        self._payload_trims = 0
        self._total_payload_bytes = 0
        self._max_payload_bytes = 0
        self._total_frames_emitted = 0
        self._total_frames_filtered = 0
        self._reconfigurations = 0
        self._handler_failures = 0

    # ── recording ────────────────────────────────────────────────────────
    def record_outcome(self) -> None:
        with self._lock:
            self._outcomes_observed += 1

    def record_capture_attempted(self) -> None:
        with self._lock:
            self._captures_attempted += 1

    def record_capture_emitted(
        self, *, payload_bytes: int, frame_count: int, filtered_count: int, trimmed: bool
    ) -> None:
        with self._lock:
            self._captures_emitted += 1
            self._total_payload_bytes += payload_bytes
            if payload_bytes > self._max_payload_bytes:
                self._max_payload_bytes = payload_bytes
            self._total_frames_emitted += frame_count
            self._total_frames_filtered += filtered_count
            if trimmed:
                self._payload_trims += 1

    def record_capture_dropped_backpressure(self) -> None:
        with self._lock:
            self._captures_dropped_backpressure += 1

    def record_capture_dropped_emitter(self) -> None:
        with self._lock:
            self._captures_dropped_emitter += 1

    def record_capture_skipped_policy(self) -> None:
        with self._lock:
            self._captures_skipped_policy += 1

    def record_capture_skipped_reentry(self) -> None:
        with self._lock:
            self._captures_skipped_reentry += 1

    def record_sampler_failure(self) -> None:
        with self._lock:
            self._sampler_failures += 1

    def record_serializer_failure(self) -> None:
        with self._lock:
            self._serializer_failures += 1

    def record_emitter_failure(self) -> None:
        with self._lock:
            self._emitter_failures += 1

    def record_reconfiguration(self) -> None:
        with self._lock:
            self._reconfigurations += 1

    def record_handler_failure(self) -> None:
        with self._lock:
            self._handler_failures += 1

    # ── snapshot ─────────────────────────────────────────────────────────
    def snapshot(self) -> StackCaptureMetricsSnapshot:
        with self._lock:
            return StackCaptureMetricsSnapshot(
                outcomes_observed=self._outcomes_observed,
                captures_attempted=self._captures_attempted,
                captures_emitted=self._captures_emitted,
                captures_dropped_backpressure=self._captures_dropped_backpressure,
                captures_dropped_emitter=self._captures_dropped_emitter,
                captures_skipped_policy=self._captures_skipped_policy,
                captures_skipped_reentry=self._captures_skipped_reentry,
                sampler_failures=self._sampler_failures,
                serializer_failures=self._serializer_failures,
                emitter_failures=self._emitter_failures,
                payload_trims=self._payload_trims,
                total_payload_bytes=self._total_payload_bytes,
                max_payload_bytes_observed=self._max_payload_bytes,
                total_frames_emitted=self._total_frames_emitted,
                total_frames_filtered=self._total_frames_filtered,
                reconfigurations=self._reconfigurations,
                handler_failures=self._handler_failures,
            )
