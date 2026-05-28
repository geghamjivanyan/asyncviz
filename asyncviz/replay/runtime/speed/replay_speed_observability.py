"""Process-wide speed-coordination metrics."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpeedMetricsSnapshot:
    requested: int = 0
    applied: int = 0
    coalesced: int = 0
    rejected: int = 0
    clamped: int = 0
    transitions_recorded: int = 0
    cumulative_latency_ns: int = 0
    max_latency_ns: int = 0
    coordination_drops: int = 0
    integrity_violations: int = 0
    drift_samples: int = 0
    cumulative_drift_abs_ns: int = 0
    max_drift_abs_ns: int = 0
    invalid_speed_inputs: int = 0


class _SpeedMetrics:
    __slots__ = (
        "_applied",
        "_clamped",
        "_coalesced",
        "_coordination_drops",
        "_cumulative_drift_abs_ns",
        "_cumulative_latency_ns",
        "_drift_samples",
        "_integrity_violations",
        "_invalid_speed_inputs",
        "_lock",
        "_max_drift_abs_ns",
        "_max_latency_ns",
        "_rejected",
        "_requested",
        "_transitions_recorded",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reset_locked()

    def _reset_locked(self) -> None:
        self._requested = 0
        self._applied = 0
        self._coalesced = 0
        self._rejected = 0
        self._clamped = 0
        self._transitions_recorded = 0
        self._cumulative_latency_ns = 0
        self._max_latency_ns = 0
        self._coordination_drops = 0
        self._integrity_violations = 0
        self._drift_samples = 0
        self._cumulative_drift_abs_ns = 0
        self._max_drift_abs_ns = 0
        self._invalid_speed_inputs = 0

    def record_requested(self) -> None:
        with self._lock:
            self._requested += 1

    def record_applied(self, latency_ns: int) -> None:
        with self._lock:
            self._applied += 1
            self._cumulative_latency_ns += max(0, latency_ns)
            if latency_ns > self._max_latency_ns:
                self._max_latency_ns = latency_ns

    def record_coalesced(self) -> None:
        with self._lock:
            self._coalesced += 1

    def record_rejected(self) -> None:
        with self._lock:
            self._rejected += 1

    def record_clamped(self) -> None:
        with self._lock:
            self._clamped += 1

    def record_transition(self) -> None:
        with self._lock:
            self._transitions_recorded += 1

    def record_coordination_drop(self) -> None:
        with self._lock:
            self._coordination_drops += 1

    def record_integrity_violation(self) -> None:
        with self._lock:
            self._integrity_violations += 1

    def record_drift_sample(self, drift_ns: int) -> None:
        magnitude = abs(drift_ns)
        with self._lock:
            self._drift_samples += 1
            self._cumulative_drift_abs_ns += magnitude
            if magnitude > self._max_drift_abs_ns:
                self._max_drift_abs_ns = magnitude

    def record_invalid_speed(self) -> None:
        with self._lock:
            self._invalid_speed_inputs += 1

    def snapshot(self) -> SpeedMetricsSnapshot:
        with self._lock:
            return SpeedMetricsSnapshot(
                requested=self._requested,
                applied=self._applied,
                coalesced=self._coalesced,
                rejected=self._rejected,
                clamped=self._clamped,
                transitions_recorded=self._transitions_recorded,
                cumulative_latency_ns=self._cumulative_latency_ns,
                max_latency_ns=self._max_latency_ns,
                coordination_drops=self._coordination_drops,
                integrity_violations=self._integrity_violations,
                drift_samples=self._drift_samples,
                cumulative_drift_abs_ns=self._cumulative_drift_abs_ns,
                max_drift_abs_ns=self._max_drift_abs_ns,
                invalid_speed_inputs=self._invalid_speed_inputs,
            )

    def reset(self) -> None:
        with self._lock:
            self._reset_locked()


_METRICS: _SpeedMetrics | None = None
_METRICS_LOCK = threading.Lock()


def get_speed_metrics() -> _SpeedMetrics:
    global _METRICS
    if _METRICS is None:
        with _METRICS_LOCK:
            if _METRICS is None:
                _METRICS = _SpeedMetrics()
    return _METRICS


def get_speed_metrics_snapshot() -> SpeedMetricsSnapshot:
    return get_speed_metrics().snapshot()


def reset_speed_metrics() -> None:
    if _METRICS is not None:
        _METRICS.reset()
