"""Process-wide playback-coordination counters."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlaybackCoordinationMetricsSnapshot:
    pauses_requested: int = 0
    pauses_completed: int = 0
    resumes_requested: int = 0
    resumes_completed: int = 0
    steps_requested: int = 0
    steps_completed: int = 0
    pause_barriers_resolved: int = 0
    resume_barriers_resolved: int = 0
    transition_violations: int = 0
    coordination_drops: int = 0
    backpressure_events: int = 0
    cumulative_pause_latency_ns: int = 0
    max_pause_latency_ns: int = 0
    cumulative_resume_latency_ns: int = 0
    max_resume_latency_ns: int = 0
    pause_budget_exceeded: int = 0
    coalesced_requests: int = 0


class _CoordinationMetrics:
    __slots__ = (
        "_backpressure_events",
        "_coalesced",
        "_coordination_drops",
        "_cumulative_pause_latency",
        "_cumulative_resume_latency",
        "_lock",
        "_max_pause_latency",
        "_max_resume_latency",
        "_pause_barriers",
        "_pause_budget_exceeded",
        "_pauses_completed",
        "_pauses_requested",
        "_resume_barriers",
        "_resumes_completed",
        "_resumes_requested",
        "_steps_completed",
        "_steps_requested",
        "_transition_violations",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reset_locked()

    def _reset_locked(self) -> None:
        self._pauses_requested = 0
        self._pauses_completed = 0
        self._resumes_requested = 0
        self._resumes_completed = 0
        self._steps_requested = 0
        self._steps_completed = 0
        self._pause_barriers = 0
        self._resume_barriers = 0
        self._transition_violations = 0
        self._coordination_drops = 0
        self._backpressure_events = 0
        self._cumulative_pause_latency = 0
        self._max_pause_latency = 0
        self._cumulative_resume_latency = 0
        self._max_resume_latency = 0
        self._pause_budget_exceeded = 0
        self._coalesced = 0

    # ── mutators ──────────────────────────────────────────────────

    def record_pause_requested(self) -> None:
        with self._lock:
            self._pauses_requested += 1

    def record_pause_completed(self, latency_ns: int) -> None:
        with self._lock:
            self._pauses_completed += 1
            self._cumulative_pause_latency += max(0, latency_ns)
            if latency_ns > self._max_pause_latency:
                self._max_pause_latency = latency_ns

    def record_resume_requested(self) -> None:
        with self._lock:
            self._resumes_requested += 1

    def record_resume_completed(self, latency_ns: int) -> None:
        with self._lock:
            self._resumes_completed += 1
            self._cumulative_resume_latency += max(0, latency_ns)
            if latency_ns > self._max_resume_latency:
                self._max_resume_latency = latency_ns

    def record_step_requested(self) -> None:
        with self._lock:
            self._steps_requested += 1

    def record_step_completed(self) -> None:
        with self._lock:
            self._steps_completed += 1

    def record_pause_barrier_resolved(self) -> None:
        with self._lock:
            self._pause_barriers += 1

    def record_resume_barrier_resolved(self) -> None:
        with self._lock:
            self._resume_barriers += 1

    def record_transition_violation(self) -> None:
        with self._lock:
            self._transition_violations += 1

    def record_coordination_drop(self) -> None:
        with self._lock:
            self._coordination_drops += 1

    def record_backpressure_event(self) -> None:
        with self._lock:
            self._backpressure_events += 1

    def record_pause_budget_exceeded(self) -> None:
        with self._lock:
            self._pause_budget_exceeded += 1

    def record_coalesced_request(self) -> None:
        with self._lock:
            self._coalesced += 1

    def snapshot(self) -> PlaybackCoordinationMetricsSnapshot:
        with self._lock:
            return PlaybackCoordinationMetricsSnapshot(
                pauses_requested=self._pauses_requested,
                pauses_completed=self._pauses_completed,
                resumes_requested=self._resumes_requested,
                resumes_completed=self._resumes_completed,
                steps_requested=self._steps_requested,
                steps_completed=self._steps_completed,
                pause_barriers_resolved=self._pause_barriers,
                resume_barriers_resolved=self._resume_barriers,
                transition_violations=self._transition_violations,
                coordination_drops=self._coordination_drops,
                backpressure_events=self._backpressure_events,
                cumulative_pause_latency_ns=self._cumulative_pause_latency,
                max_pause_latency_ns=self._max_pause_latency,
                cumulative_resume_latency_ns=self._cumulative_resume_latency,
                max_resume_latency_ns=self._max_resume_latency,
                pause_budget_exceeded=self._pause_budget_exceeded,
                coalesced_requests=self._coalesced,
            )

    def reset(self) -> None:
        with self._lock:
            self._reset_locked()


_METRICS: _CoordinationMetrics | None = None
_METRICS_LOCK = threading.Lock()


def get_coordination_metrics() -> _CoordinationMetrics:
    global _METRICS
    if _METRICS is None:
        with _METRICS_LOCK:
            if _METRICS is None:
                _METRICS = _CoordinationMetrics()
    return _METRICS


def get_coordination_metrics_snapshot() -> PlaybackCoordinationMetricsSnapshot:
    return get_coordination_metrics().snapshot()


def reset_coordination_metrics() -> None:
    if _METRICS is not None:
        _METRICS.reset()
