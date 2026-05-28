"""Replay-engine observability counters.

Mirrors the structure of the format/loader metric singletons.
Tracks lifecycle, dispatch, scheduling drift, seek cost, checkpoint
activity, integrity violations, backpressure events."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReplayEngineMetricsSnapshot:
    """Immutable diagnostics view of the engine metrics."""

    engines_started: int = 0
    engines_stopped: int = 0
    frames_dispatched: int = 0
    reducer_invocations: int = 0
    seeks_performed: int = 0
    pauses: int = 0
    resumes: int = 0
    speed_changes: int = 0
    checkpoints_recorded: int = 0
    snapshots_restored: int = 0
    integrity_violations: int = 0
    backpressure_events: int = 0
    sink_failures: int = 0
    scheduler_skips: int = 0
    cumulative_lag_ns: int = 0
    max_lag_ns: int = 0


class _EngineMetrics:
    __slots__ = (
        "_backpressure_events",
        "_checkpoints_recorded",
        "_cumulative_lag_ns",
        "_engines_started",
        "_engines_stopped",
        "_frames_dispatched",
        "_integrity_violations",
        "_lock",
        "_max_lag_ns",
        "_pauses",
        "_reducer_invocations",
        "_resumes",
        "_scheduler_skips",
        "_seeks_performed",
        "_sink_failures",
        "_snapshots_restored",
        "_speed_changes",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reset_locked()

    def _reset_locked(self) -> None:
        self._engines_started = 0
        self._engines_stopped = 0
        self._frames_dispatched = 0
        self._reducer_invocations = 0
        self._seeks_performed = 0
        self._pauses = 0
        self._resumes = 0
        self._speed_changes = 0
        self._checkpoints_recorded = 0
        self._snapshots_restored = 0
        self._integrity_violations = 0
        self._backpressure_events = 0
        self._sink_failures = 0
        self._scheduler_skips = 0
        self._cumulative_lag_ns = 0
        self._max_lag_ns = 0

    # ── mutators ──────────────────────────────────────────────────

    def record_engine_started(self) -> None:
        with self._lock:
            self._engines_started += 1

    def record_engine_stopped(self) -> None:
        with self._lock:
            self._engines_stopped += 1

    def record_frame_dispatched(self) -> None:
        with self._lock:
            self._frames_dispatched += 1

    def record_reducer_invocation(self) -> None:
        with self._lock:
            self._reducer_invocations += 1

    def record_seek(self) -> None:
        with self._lock:
            self._seeks_performed += 1

    def record_pause(self) -> None:
        with self._lock:
            self._pauses += 1

    def record_resume(self) -> None:
        with self._lock:
            self._resumes += 1

    def record_speed_change(self) -> None:
        with self._lock:
            self._speed_changes += 1

    def record_checkpoint(self) -> None:
        with self._lock:
            self._checkpoints_recorded += 1

    def record_snapshot_restored(self) -> None:
        with self._lock:
            self._snapshots_restored += 1

    def record_integrity_violation(self) -> None:
        with self._lock:
            self._integrity_violations += 1

    def record_backpressure_event(self) -> None:
        with self._lock:
            self._backpressure_events += 1

    def record_sink_failure(self) -> None:
        with self._lock:
            self._sink_failures += 1

    def record_scheduler_skip(self) -> None:
        with self._lock:
            self._scheduler_skips += 1

    def record_lag(self, lag_ns: int) -> None:
        if lag_ns <= 0:
            return
        with self._lock:
            self._cumulative_lag_ns += lag_ns
            if lag_ns > self._max_lag_ns:
                self._max_lag_ns = lag_ns

    def snapshot(self) -> ReplayEngineMetricsSnapshot:
        with self._lock:
            return ReplayEngineMetricsSnapshot(
                engines_started=self._engines_started,
                engines_stopped=self._engines_stopped,
                frames_dispatched=self._frames_dispatched,
                reducer_invocations=self._reducer_invocations,
                seeks_performed=self._seeks_performed,
                pauses=self._pauses,
                resumes=self._resumes,
                speed_changes=self._speed_changes,
                checkpoints_recorded=self._checkpoints_recorded,
                snapshots_restored=self._snapshots_restored,
                integrity_violations=self._integrity_violations,
                backpressure_events=self._backpressure_events,
                sink_failures=self._sink_failures,
                scheduler_skips=self._scheduler_skips,
                cumulative_lag_ns=self._cumulative_lag_ns,
                max_lag_ns=self._max_lag_ns,
            )

    def reset(self) -> None:
        with self._lock:
            self._reset_locked()


_METRICS: _EngineMetrics | None = None
_METRICS_LOCK = threading.Lock()


def get_engine_metrics() -> _EngineMetrics:
    global _METRICS
    if _METRICS is None:
        with _METRICS_LOCK:
            if _METRICS is None:
                _METRICS = _EngineMetrics()
    return _METRICS


def get_engine_metrics_snapshot() -> ReplayEngineMetricsSnapshot:
    return get_engine_metrics().snapshot()


def reset_engine_metrics() -> None:
    if _METRICS is not None:
        _METRICS.reset()
