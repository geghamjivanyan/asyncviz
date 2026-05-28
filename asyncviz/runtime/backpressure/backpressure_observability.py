"""Process-wide backpressure metrics."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BackpressureMetricsSnapshot:
    controllers_started: int = 0
    controllers_reset: int = 0
    state_transitions: int = 0
    emergency_entries: int = 0
    events_accepted: int = 0
    events_rejected: int = 0
    events_evicted: int = 0
    websocket_disconnects: int = 0
    overflow_markers_emitted: int = 0
    actions_dispatched: int = 0
    integrity_violations: int = 0


class _BackpressureMetrics:
    __slots__ = (
        "_actions_dispatched",
        "_controllers_reset",
        "_controllers_started",
        "_emergency_entries",
        "_events_accepted",
        "_events_evicted",
        "_events_rejected",
        "_integrity_violations",
        "_lock",
        "_overflow_markers_emitted",
        "_state_transitions",
        "_websocket_disconnects",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reset_locked()

    def _reset_locked(self) -> None:
        self._controllers_started = 0
        self._controllers_reset = 0
        self._state_transitions = 0
        self._emergency_entries = 0
        self._events_accepted = 0
        self._events_rejected = 0
        self._events_evicted = 0
        self._websocket_disconnects = 0
        self._overflow_markers_emitted = 0
        self._actions_dispatched = 0
        self._integrity_violations = 0

    def record_controller_started(self) -> None:
        with self._lock:
            self._controllers_started += 1

    def record_controller_reset(self) -> None:
        with self._lock:
            self._controllers_reset += 1

    def record_state_transition(self, *, emergency: bool) -> None:
        with self._lock:
            self._state_transitions += 1
            if emergency:
                self._emergency_entries += 1

    def record_event_accepted(self) -> None:
        with self._lock:
            self._events_accepted += 1

    def record_event_rejected(self) -> None:
        with self._lock:
            self._events_rejected += 1

    def record_event_evicted(self) -> None:
        with self._lock:
            self._events_evicted += 1

    def record_websocket_disconnect(self) -> None:
        with self._lock:
            self._websocket_disconnects += 1

    def record_overflow_marker(self) -> None:
        with self._lock:
            self._overflow_markers_emitted += 1

    def record_action_dispatched(self) -> None:
        with self._lock:
            self._actions_dispatched += 1

    def record_integrity_violation(self) -> None:
        with self._lock:
            self._integrity_violations += 1

    def snapshot(self) -> BackpressureMetricsSnapshot:
        with self._lock:
            return BackpressureMetricsSnapshot(
                controllers_started=self._controllers_started,
                controllers_reset=self._controllers_reset,
                state_transitions=self._state_transitions,
                emergency_entries=self._emergency_entries,
                events_accepted=self._events_accepted,
                events_rejected=self._events_rejected,
                events_evicted=self._events_evicted,
                websocket_disconnects=self._websocket_disconnects,
                overflow_markers_emitted=self._overflow_markers_emitted,
                actions_dispatched=self._actions_dispatched,
                integrity_violations=self._integrity_violations,
            )

    def reset(self) -> None:
        with self._lock:
            self._reset_locked()


_METRICS: _BackpressureMetrics | None = None
_METRICS_LOCK = threading.Lock()


def get_backpressure_metrics() -> _BackpressureMetrics:
    global _METRICS
    if _METRICS is None:
        with _METRICS_LOCK:
            if _METRICS is None:
                _METRICS = _BackpressureMetrics()
    return _METRICS


def get_backpressure_metrics_snapshot() -> BackpressureMetricsSnapshot:
    return get_backpressure_metrics().snapshot()


def reset_backpressure_metrics() -> None:
    if _METRICS is not None:
        _METRICS.reset()
