"""Singleton compatibility metrics.

Mirrors the established pattern: thread-safe counters, frozen
snapshot, module-level singleton reset-able for tests.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LoopCompatMetricsSnapshot:
    managers_attached: int
    uvloop_installs_attempted: int
    uvloop_installs_succeeded: int
    uvloop_installs_failed: int
    fallback_activations: int
    drift_warnings: int
    integrity_violations: int
    replay_drift_frames: int
    websocket_cadence_deviations: int
    scheduler_past_due: int
    by_loop_kind: dict[str, int]


class LoopCompatMetrics:
    """Per-process metric aggregator."""

    __slots__ = (
        "_by_loop_kind",
        "_drift_warnings",
        "_fallback_activations",
        "_integrity_violations",
        "_lock",
        "_managers_attached",
        "_replay_drift_frames",
        "_scheduler_past_due",
        "_uvloop_installs_attempted",
        "_uvloop_installs_failed",
        "_uvloop_installs_succeeded",
        "_websocket_cadence_deviations",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._managers_attached = 0
        self._uvloop_installs_attempted = 0
        self._uvloop_installs_succeeded = 0
        self._uvloop_installs_failed = 0
        self._fallback_activations = 0
        self._drift_warnings = 0
        self._integrity_violations = 0
        self._replay_drift_frames = 0
        self._websocket_cadence_deviations = 0
        self._scheduler_past_due = 0
        self._by_loop_kind: dict[str, int] = {}

    def record_manager_attached(self, kind: str) -> None:
        with self._lock:
            self._managers_attached += 1
            self._by_loop_kind[kind] = self._by_loop_kind.get(kind, 0) + 1

    def record_uvloop_install_attempt(self) -> None:
        with self._lock:
            self._uvloop_installs_attempted += 1

    def record_uvloop_install_success(self) -> None:
        with self._lock:
            self._uvloop_installs_succeeded += 1

    def record_uvloop_install_failure(self) -> None:
        with self._lock:
            self._uvloop_installs_failed += 1

    def record_fallback_activation(self, count: int = 1) -> None:
        with self._lock:
            self._fallback_activations += count

    def record_drift_warning(self, count: int = 1) -> None:
        with self._lock:
            self._drift_warnings += count

    def record_integrity_violation(self, count: int = 1) -> None:
        with self._lock:
            self._integrity_violations += count

    def record_replay_drift_frame(self, count: int = 1) -> None:
        with self._lock:
            self._replay_drift_frames += count

    def record_websocket_cadence_deviation(self, count: int = 1) -> None:
        with self._lock:
            self._websocket_cadence_deviations += count

    def record_scheduler_past_due(self, count: int = 1) -> None:
        with self._lock:
            self._scheduler_past_due += count

    def snapshot(self) -> LoopCompatMetricsSnapshot:
        with self._lock:
            return LoopCompatMetricsSnapshot(
                managers_attached=self._managers_attached,
                uvloop_installs_attempted=self._uvloop_installs_attempted,
                uvloop_installs_succeeded=self._uvloop_installs_succeeded,
                uvloop_installs_failed=self._uvloop_installs_failed,
                fallback_activations=self._fallback_activations,
                drift_warnings=self._drift_warnings,
                integrity_violations=self._integrity_violations,
                replay_drift_frames=self._replay_drift_frames,
                websocket_cadence_deviations=self._websocket_cadence_deviations,
                scheduler_past_due=self._scheduler_past_due,
                by_loop_kind=dict(self._by_loop_kind),
            )

    def reset(self) -> None:
        with self._lock:
            self._managers_attached = 0
            self._uvloop_installs_attempted = 0
            self._uvloop_installs_succeeded = 0
            self._uvloop_installs_failed = 0
            self._fallback_activations = 0
            self._drift_warnings = 0
            self._integrity_violations = 0
            self._replay_drift_frames = 0
            self._websocket_cadence_deviations = 0
            self._scheduler_past_due = 0
            self._by_loop_kind = {}


_instance: LoopCompatMetrics | None = None
_instance_lock = threading.Lock()


def get_loop_compat_metrics() -> LoopCompatMetrics:
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = LoopCompatMetrics()
        return _instance


def get_loop_compat_metrics_snapshot() -> LoopCompatMetricsSnapshot:
    return get_loop_compat_metrics().snapshot()


def reset_loop_compat_metrics() -> None:
    with _instance_lock:
        if _instance is not None:
            _instance.reset()
