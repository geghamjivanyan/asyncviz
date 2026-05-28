"""Singleton stress metrics.

Mirrors the established pattern: thread-safe counters, frozen
snapshot view, module-level singleton reset-able for tests.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class StressMetricsSnapshot:
    """Frozen view of the stress-runner counters."""

    scenarios_started: int
    scenarios_completed: int
    scenarios_failed: int
    scenarios_warned: int
    scenarios_errored: int
    scenarios_skipped: int
    operations_completed: int
    operations_failed: int
    overload_transitions: int
    emergency_actions: int
    websocket_disconnects: int
    replay_frames_streamed: int
    render_frames_rendered: int
    failure_injections: int
    threshold_violations: int
    survivability_score_sum: float
    survivability_score_samples: int
    survivability_score_mean: float
    by_category: dict[str, int] = field(default_factory=dict)


class StressMetrics:
    """Per-suite metric aggregator."""

    __slots__ = (
        "_by_category",
        "_emergency_actions",
        "_failure_injections",
        "_lock",
        "_operations_completed",
        "_operations_failed",
        "_overload_transitions",
        "_render_frames_rendered",
        "_replay_frames_streamed",
        "_scenarios_completed",
        "_scenarios_errored",
        "_scenarios_failed",
        "_scenarios_skipped",
        "_scenarios_started",
        "_scenarios_warned",
        "_survivability_score_samples",
        "_survivability_score_sum",
        "_threshold_violations",
        "_websocket_disconnects",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._scenarios_started = 0
        self._scenarios_completed = 0
        self._scenarios_failed = 0
        self._scenarios_warned = 0
        self._scenarios_errored = 0
        self._scenarios_skipped = 0
        self._operations_completed = 0
        self._operations_failed = 0
        self._overload_transitions = 0
        self._emergency_actions = 0
        self._websocket_disconnects = 0
        self._replay_frames_streamed = 0
        self._render_frames_rendered = 0
        self._failure_injections = 0
        self._threshold_violations = 0
        self._survivability_score_sum = 0.0
        self._survivability_score_samples = 0
        self._by_category: dict[str, int] = {}

    # ── recorders ─────────────────────────────────────────────────

    def record_scenario_started(self, category: str) -> None:
        with self._lock:
            self._scenarios_started += 1
            self._by_category[category] = self._by_category.get(category, 0) + 1

    def record_scenario_completed(self) -> None:
        with self._lock:
            self._scenarios_completed += 1

    def record_scenario_verdict(self, verdict: str) -> None:
        with self._lock:
            if verdict == "failed":
                self._scenarios_failed += 1
            elif verdict == "warned":
                self._scenarios_warned += 1
            elif verdict == "errored":
                self._scenarios_errored += 1
            elif verdict == "skipped":
                self._scenarios_skipped += 1

    def record_operation_completed(self, count: int = 1) -> None:
        with self._lock:
            self._operations_completed += count

    def record_operation_failed(self, count: int = 1) -> None:
        with self._lock:
            self._operations_failed += count

    def record_overload_transition(self) -> None:
        with self._lock:
            self._overload_transitions += 1

    def record_emergency_action(self) -> None:
        with self._lock:
            self._emergency_actions += 1

    def record_websocket_disconnect(self, count: int = 1) -> None:
        with self._lock:
            self._websocket_disconnects += count

    def record_replay_frame(self, count: int = 1) -> None:
        with self._lock:
            self._replay_frames_streamed += count

    def record_render_frame(self, count: int = 1) -> None:
        with self._lock:
            self._render_frames_rendered += count

    def record_failure_injection(self) -> None:
        with self._lock:
            self._failure_injections += 1

    def record_threshold_violation(self, count: int = 1) -> None:
        with self._lock:
            self._threshold_violations += count

    def record_survivability_score(self, score: float) -> None:
        with self._lock:
            self._survivability_score_sum += score
            self._survivability_score_samples += 1

    # ── snapshot / reset ──────────────────────────────────────────

    def snapshot(self) -> StressMetricsSnapshot:
        with self._lock:
            mean = (
                self._survivability_score_sum / self._survivability_score_samples
                if self._survivability_score_samples > 0
                else 0.0
            )
            return StressMetricsSnapshot(
                scenarios_started=self._scenarios_started,
                scenarios_completed=self._scenarios_completed,
                scenarios_failed=self._scenarios_failed,
                scenarios_warned=self._scenarios_warned,
                scenarios_errored=self._scenarios_errored,
                scenarios_skipped=self._scenarios_skipped,
                operations_completed=self._operations_completed,
                operations_failed=self._operations_failed,
                overload_transitions=self._overload_transitions,
                emergency_actions=self._emergency_actions,
                websocket_disconnects=self._websocket_disconnects,
                replay_frames_streamed=self._replay_frames_streamed,
                render_frames_rendered=self._render_frames_rendered,
                failure_injections=self._failure_injections,
                threshold_violations=self._threshold_violations,
                survivability_score_sum=self._survivability_score_sum,
                survivability_score_samples=self._survivability_score_samples,
                survivability_score_mean=mean,
                by_category=dict(self._by_category),
            )

    def reset(self) -> None:
        with self._lock:
            self._scenarios_started = 0
            self._scenarios_completed = 0
            self._scenarios_failed = 0
            self._scenarios_warned = 0
            self._scenarios_errored = 0
            self._scenarios_skipped = 0
            self._operations_completed = 0
            self._operations_failed = 0
            self._overload_transitions = 0
            self._emergency_actions = 0
            self._websocket_disconnects = 0
            self._replay_frames_streamed = 0
            self._render_frames_rendered = 0
            self._failure_injections = 0
            self._threshold_violations = 0
            self._survivability_score_sum = 0.0
            self._survivability_score_samples = 0
            self._by_category = {}


_instance: StressMetrics | None = None
_instance_lock = threading.Lock()


def get_stress_metrics() -> StressMetrics:
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = StressMetrics()
        return _instance


def get_stress_metrics_snapshot() -> StressMetricsSnapshot:
    return get_stress_metrics().snapshot()


def reset_stress_metrics() -> None:
    with _instance_lock:
        if _instance is not None:
            _instance.reset()
