"""Self-observability counters for :class:`RuntimeStreamingEngine`."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StreamingMetricsSnapshot:
    """Immutable view of :class:`StreamingMetrics`."""

    metrics_deltas_sent: int
    warning_deltas_sent: int
    timeline_deltas_sent: int
    runtime_deltas_sent: int
    protocol_errors_sent: int
    subscription_dispatches: int
    subscription_failures: int
    broadcast_failures: int


class StreamingMetrics:
    """Thread-safe counters for the streaming engine.

    Read by ``/api/runtime/streaming`` and embedded in the engine's
    snapshot. Each subsystem stream has its own counter so operators can
    see which channel is dominating.
    """

    __slots__ = (
        "_broadcast_failures",
        "_lock",
        "_metrics_deltas_sent",
        "_protocol_errors_sent",
        "_runtime_deltas_sent",
        "_subscription_dispatches",
        "_subscription_failures",
        "_timeline_deltas_sent",
        "_warning_deltas_sent",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._metrics_deltas_sent = 0
        self._warning_deltas_sent = 0
        self._timeline_deltas_sent = 0
        self._runtime_deltas_sent = 0
        self._protocol_errors_sent = 0
        self._subscription_dispatches = 0
        self._subscription_failures = 0
        self._broadcast_failures = 0

    def record_metrics_delta(self, n: int = 1) -> None:
        with self._lock:
            self._metrics_deltas_sent += n

    def record_warning_delta(self, n: int = 1) -> None:
        with self._lock:
            self._warning_deltas_sent += n

    def record_timeline_delta(self, n: int = 1) -> None:
        with self._lock:
            self._timeline_deltas_sent += n

    def record_runtime_delta(self, n: int = 1) -> None:
        with self._lock:
            self._runtime_deltas_sent += n

    def record_protocol_error(self) -> None:
        with self._lock:
            self._protocol_errors_sent += 1

    def record_subscription_dispatch(self, *, failed: bool = False) -> None:
        with self._lock:
            self._subscription_dispatches += 1
            if failed:
                self._subscription_failures += 1

    def record_broadcast_failure(self) -> None:
        with self._lock:
            self._broadcast_failures += 1

    def reset(self) -> None:
        with self._lock:
            self._metrics_deltas_sent = 0
            self._warning_deltas_sent = 0
            self._timeline_deltas_sent = 0
            self._runtime_deltas_sent = 0
            self._protocol_errors_sent = 0
            self._subscription_dispatches = 0
            self._subscription_failures = 0
            self._broadcast_failures = 0

    def snapshot(self) -> StreamingMetricsSnapshot:
        with self._lock:
            return StreamingMetricsSnapshot(
                metrics_deltas_sent=self._metrics_deltas_sent,
                warning_deltas_sent=self._warning_deltas_sent,
                timeline_deltas_sent=self._timeline_deltas_sent,
                runtime_deltas_sent=self._runtime_deltas_sent,
                protocol_errors_sent=self._protocol_errors_sent,
                subscription_dispatches=self._subscription_dispatches,
                subscription_failures=self._subscription_failures,
                broadcast_failures=self._broadcast_failures,
            )
