"""Self-observability counters for :class:`HealthService`."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HealthMetricsSnapshot:
    """Immutable view of :class:`HealthMetrics`."""

    evaluations_total: int
    liveness_checks: int
    readiness_checks: int
    full_checks: int
    runtime_diagnostics_calls: int
    degraded_evaluations: int
    unavailable_evaluations: int
    probe_failures: int
    total_evaluation_ns: int
    max_evaluation_ns: int
    last_evaluation_ns: int

    @property
    def average_evaluation_ns(self) -> float:
        if self.evaluations_total == 0:
            return 0.0
        return self.total_evaluation_ns / self.evaluations_total


class HealthMetrics:
    """Thread-safe counters for the health service.

    Captures both per-endpoint call counts (so operators can see which
    probe surface is hot) and aggregate evaluation outcomes. Probe
    failures are tracked separately from degraded outcomes — a single
    misbehaving probe shouldn't be confused with a real degradation.
    """

    __slots__ = (
        "_degraded_evaluations",
        "_evaluations_total",
        "_full_checks",
        "_last_evaluation_ns",
        "_liveness_checks",
        "_lock",
        "_max_evaluation_ns",
        "_probe_failures",
        "_readiness_checks",
        "_runtime_diagnostics_calls",
        "_total_evaluation_ns",
        "_unavailable_evaluations",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._evaluations_total = 0
        self._liveness_checks = 0
        self._readiness_checks = 0
        self._full_checks = 0
        self._runtime_diagnostics_calls = 0
        self._degraded_evaluations = 0
        self._unavailable_evaluations = 0
        self._probe_failures = 0
        self._total_evaluation_ns = 0
        self._max_evaluation_ns = 0
        self._last_evaluation_ns = 0

    def record_liveness(self) -> None:
        with self._lock:
            self._liveness_checks += 1

    def record_readiness(self) -> None:
        with self._lock:
            self._readiness_checks += 1

    def record_full_check(self) -> None:
        with self._lock:
            self._full_checks += 1

    def record_runtime_diagnostics(self) -> None:
        with self._lock:
            self._runtime_diagnostics_calls += 1

    def record_evaluation(
        self,
        *,
        duration_ns: int,
        degraded: bool,
        unavailable: bool,
        probe_failures: int,
    ) -> None:
        with self._lock:
            self._evaluations_total += 1
            self._total_evaluation_ns += duration_ns
            if duration_ns > self._max_evaluation_ns:
                self._max_evaluation_ns = duration_ns
            self._last_evaluation_ns = duration_ns
            if degraded:
                self._degraded_evaluations += 1
            if unavailable:
                self._unavailable_evaluations += 1
            self._probe_failures += probe_failures

    def reset(self) -> None:
        with self._lock:
            self._evaluations_total = 0
            self._liveness_checks = 0
            self._readiness_checks = 0
            self._full_checks = 0
            self._runtime_diagnostics_calls = 0
            self._degraded_evaluations = 0
            self._unavailable_evaluations = 0
            self._probe_failures = 0
            self._total_evaluation_ns = 0
            self._max_evaluation_ns = 0
            self._last_evaluation_ns = 0

    def snapshot(self) -> HealthMetricsSnapshot:
        with self._lock:
            return HealthMetricsSnapshot(
                evaluations_total=self._evaluations_total,
                liveness_checks=self._liveness_checks,
                readiness_checks=self._readiness_checks,
                full_checks=self._full_checks,
                runtime_diagnostics_calls=self._runtime_diagnostics_calls,
                degraded_evaluations=self._degraded_evaluations,
                unavailable_evaluations=self._unavailable_evaluations,
                probe_failures=self._probe_failures,
                total_evaluation_ns=self._total_evaluation_ns,
                max_evaluation_ns=self._max_evaluation_ns,
                last_evaluation_ns=self._last_evaluation_ns,
            )
