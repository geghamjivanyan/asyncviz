"""Singleton integration metrics."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class IntegrationMetricsSnapshot:
    scenarios_started: int
    scenarios_completed: int
    scenarios_passed: int
    scenarios_warned: int
    scenarios_failed: int
    scenarios_errored: int
    scenarios_skipped: int
    determinism_runs: int
    determinism_divergences: int
    uvloop_matrix_runs: int
    uvloop_divergences: int
    operations_completed: int
    operations_failed: int
    threshold_violations: int
    by_category: dict[str, int] = field(default_factory=dict)


class IntegrationMetrics:
    __slots__ = (
        "_by_category",
        "_determinism_divergences",
        "_determinism_runs",
        "_lock",
        "_operations_completed",
        "_operations_failed",
        "_scenarios_completed",
        "_scenarios_errored",
        "_scenarios_failed",
        "_scenarios_passed",
        "_scenarios_skipped",
        "_scenarios_started",
        "_scenarios_warned",
        "_threshold_violations",
        "_uvloop_divergences",
        "_uvloop_matrix_runs",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._scenarios_started = 0
        self._scenarios_completed = 0
        self._scenarios_passed = 0
        self._scenarios_warned = 0
        self._scenarios_failed = 0
        self._scenarios_errored = 0
        self._scenarios_skipped = 0
        self._determinism_runs = 0
        self._determinism_divergences = 0
        self._uvloop_matrix_runs = 0
        self._uvloop_divergences = 0
        self._operations_completed = 0
        self._operations_failed = 0
        self._threshold_violations = 0
        self._by_category: dict[str, int] = {}

    def record_scenario_started(self, category: str) -> None:
        with self._lock:
            self._scenarios_started += 1
            self._by_category[category] = self._by_category.get(category, 0) + 1

    def record_scenario_completed(self) -> None:
        with self._lock:
            self._scenarios_completed += 1

    def record_verdict(self, verdict: str) -> None:
        with self._lock:
            if verdict == "passed":
                self._scenarios_passed += 1
            elif verdict == "warned":
                self._scenarios_warned += 1
            elif verdict == "failed":
                self._scenarios_failed += 1
            elif verdict == "errored":
                self._scenarios_errored += 1
            elif verdict == "skipped":
                self._scenarios_skipped += 1

    def record_determinism_run(self, *, diverged: bool) -> None:
        with self._lock:
            self._determinism_runs += 1
            if diverged:
                self._determinism_divergences += 1

    def record_uvloop_run(self, *, diverged: bool) -> None:
        with self._lock:
            self._uvloop_matrix_runs += 1
            if diverged:
                self._uvloop_divergences += 1

    def record_operations(self, *, completed: int, failed: int) -> None:
        with self._lock:
            self._operations_completed += completed
            self._operations_failed += failed

    def record_threshold_violations(self, count: int) -> None:
        with self._lock:
            self._threshold_violations += count

    def snapshot(self) -> IntegrationMetricsSnapshot:
        with self._lock:
            return IntegrationMetricsSnapshot(
                scenarios_started=self._scenarios_started,
                scenarios_completed=self._scenarios_completed,
                scenarios_passed=self._scenarios_passed,
                scenarios_warned=self._scenarios_warned,
                scenarios_failed=self._scenarios_failed,
                scenarios_errored=self._scenarios_errored,
                scenarios_skipped=self._scenarios_skipped,
                determinism_runs=self._determinism_runs,
                determinism_divergences=self._determinism_divergences,
                uvloop_matrix_runs=self._uvloop_matrix_runs,
                uvloop_divergences=self._uvloop_divergences,
                operations_completed=self._operations_completed,
                operations_failed=self._operations_failed,
                threshold_violations=self._threshold_violations,
                by_category=dict(self._by_category),
            )

    def reset(self) -> None:
        with self._lock:
            self._scenarios_started = 0
            self._scenarios_completed = 0
            self._scenarios_passed = 0
            self._scenarios_warned = 0
            self._scenarios_failed = 0
            self._scenarios_errored = 0
            self._scenarios_skipped = 0
            self._determinism_runs = 0
            self._determinism_divergences = 0
            self._uvloop_matrix_runs = 0
            self._uvloop_divergences = 0
            self._operations_completed = 0
            self._operations_failed = 0
            self._threshold_violations = 0
            self._by_category = {}


_instance: IntegrationMetrics | None = None
_lock = threading.Lock()


def get_integration_metrics() -> IntegrationMetrics:
    global _instance
    with _lock:
        if _instance is None:
            _instance = IntegrationMetrics()
        return _instance


def get_integration_metrics_snapshot() -> IntegrationMetricsSnapshot:
    return get_integration_metrics().snapshot()


def reset_integration_metrics() -> None:
    with _lock:
        if _instance is not None:
            _instance.reset()
