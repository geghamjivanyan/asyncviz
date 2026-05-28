"""Singleton resilience metrics."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class IsolationMetricsSnapshot:
    subsystems_registered: int
    failures_observed: int
    breaker_trips: int
    breaker_closes: int
    recovery_attempts: int
    recovery_successes: int
    recovery_failures: int
    recovery_abandonments: int
    payload_quarantines: int
    boundary_admissions: int
    boundary_rejections: int
    mode_transitions: int
    last_mode: str
    by_subsystem: dict[str, int] = field(default_factory=dict)
    by_failure_kind: dict[str, int] = field(default_factory=dict)


class IsolationMetrics:
    """Aggregate counters for the resilience layer."""

    __slots__ = (
        "_boundary_admissions",
        "_boundary_rejections",
        "_breaker_closes",
        "_breaker_trips",
        "_by_failure_kind",
        "_by_subsystem",
        "_failures_observed",
        "_last_mode",
        "_lock",
        "_mode_transitions",
        "_payload_quarantines",
        "_recovery_abandonments",
        "_recovery_attempts",
        "_recovery_failures",
        "_recovery_successes",
        "_subsystems_registered",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subsystems_registered = 0
        self._failures_observed = 0
        self._breaker_trips = 0
        self._breaker_closes = 0
        self._recovery_attempts = 0
        self._recovery_successes = 0
        self._recovery_failures = 0
        self._recovery_abandonments = 0
        self._payload_quarantines = 0
        self._boundary_admissions = 0
        self._boundary_rejections = 0
        self._mode_transitions = 0
        self._last_mode = "normal"
        self._by_subsystem: dict[str, int] = {}
        self._by_failure_kind: dict[str, int] = {}

    def record_subsystem_registered(self) -> None:
        with self._lock:
            self._subsystems_registered += 1

    def record_failure(self, subsystem: str, kind: str) -> None:
        with self._lock:
            self._failures_observed += 1
            self._by_subsystem[subsystem] = self._by_subsystem.get(subsystem, 0) + 1
            self._by_failure_kind[kind] = self._by_failure_kind.get(kind, 0) + 1

    def record_breaker_trip(self) -> None:
        with self._lock:
            self._breaker_trips += 1

    def record_breaker_close(self) -> None:
        with self._lock:
            self._breaker_closes += 1

    def record_recovery_attempt(self, verdict: str) -> None:
        with self._lock:
            self._recovery_attempts += 1
            if verdict == "succeeded":
                self._recovery_successes += 1
            elif verdict == "failed":
                self._recovery_failures += 1
            elif verdict == "abandoned":
                self._recovery_abandonments += 1

    def record_payload_quarantine(self) -> None:
        with self._lock:
            self._payload_quarantines += 1

    def record_boundary_admission(self) -> None:
        with self._lock:
            self._boundary_admissions += 1

    def record_boundary_rejection(self) -> None:
        with self._lock:
            self._boundary_rejections += 1

    def record_mode_transition(self, mode: str) -> None:
        with self._lock:
            self._mode_transitions += 1
            self._last_mode = mode

    def snapshot(self) -> IsolationMetricsSnapshot:
        with self._lock:
            return IsolationMetricsSnapshot(
                subsystems_registered=self._subsystems_registered,
                failures_observed=self._failures_observed,
                breaker_trips=self._breaker_trips,
                breaker_closes=self._breaker_closes,
                recovery_attempts=self._recovery_attempts,
                recovery_successes=self._recovery_successes,
                recovery_failures=self._recovery_failures,
                recovery_abandonments=self._recovery_abandonments,
                payload_quarantines=self._payload_quarantines,
                boundary_admissions=self._boundary_admissions,
                boundary_rejections=self._boundary_rejections,
                mode_transitions=self._mode_transitions,
                last_mode=self._last_mode,
                by_subsystem=dict(self._by_subsystem),
                by_failure_kind=dict(self._by_failure_kind),
            )

    def reset(self) -> None:
        with self._lock:
            self._subsystems_registered = 0
            self._failures_observed = 0
            self._breaker_trips = 0
            self._breaker_closes = 0
            self._recovery_attempts = 0
            self._recovery_successes = 0
            self._recovery_failures = 0
            self._recovery_abandonments = 0
            self._payload_quarantines = 0
            self._boundary_admissions = 0
            self._boundary_rejections = 0
            self._mode_transitions = 0
            self._last_mode = "normal"
            self._by_subsystem = {}
            self._by_failure_kind = {}


_instance: IsolationMetrics | None = None
_instance_lock = threading.Lock()


def get_isolation_metrics() -> IsolationMetrics:
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = IsolationMetrics()
        return _instance


def get_isolation_metrics_snapshot() -> IsolationMetricsSnapshot:
    return get_isolation_metrics().snapshot()


def reset_isolation_metrics() -> None:
    with _instance_lock:
        if _instance is not None:
            _instance.reset()
