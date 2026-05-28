"""Backend-side request/operation counters.

Distinct from :class:`asyncviz.runtime.metrics.RuntimeMetricsAggregator`
which tracks *asyncio task lifecycle* analytics — this module tracks the
*FastAPI server's* own observability surface: request count, duration
percentiles, error rates, websocket connect/disconnect counts.
"""

from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class BackendMetricsSnapshot:
    """Immutable view of :class:`BackendMetrics`."""

    requests_total: int
    requests_in_flight: int
    requests_by_status: dict[str, int]
    requests_by_method: dict[str, int]
    average_duration_ms: float
    max_duration_ms: float
    api_errors_total: int
    api_errors_by_code: dict[str, int]
    ws_connections_total: int
    ws_disconnections_total: int
    ws_active_connections: int


@dataclass(slots=True)
class _Aggregates:
    """Running aggregate state behind the lock."""

    requests_total: int = 0
    requests_in_flight: int = 0
    total_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    api_errors_total: int = 0
    ws_connections_total: int = 0
    ws_disconnections_total: int = 0
    by_status: Counter[str] = field(default_factory=Counter)
    by_method: Counter[str] = field(default_factory=Counter)
    by_error_code: Counter[str] = field(default_factory=Counter)


class BackendMetrics:
    """Thread-safe counters for the backend's own request / WS lifecycle.

    Used by the middleware layer to record per-request timings and by the
    websocket gateway to track connection counts. Read by the
    ``/api/runtime/backend`` endpoint.
    """

    __slots__ = ("_aggregates", "_lock")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._aggregates = _Aggregates()

    # ── request lifecycle ────────────────────────────────────────────────
    def begin_request(self) -> None:
        with self._lock:
            self._aggregates.requests_in_flight += 1

    def end_request(self) -> None:
        with self._lock:
            if self._aggregates.requests_in_flight > 0:
                self._aggregates.requests_in_flight -= 1

    def record_request(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        del path  # reserved for future path-bucketing
        with self._lock:
            agg = self._aggregates
            agg.requests_total += 1
            agg.total_duration_ms += duration_ms
            if duration_ms > agg.max_duration_ms:
                agg.max_duration_ms = duration_ms
            agg.by_status[str(status_code)] += 1
            agg.by_method[method.upper()] += 1

    def record_api_error(self, code: str) -> None:
        with self._lock:
            self._aggregates.api_errors_total += 1
            self._aggregates.by_error_code[code] += 1

    # ── websocket lifecycle ──────────────────────────────────────────────
    def record_ws_connect(self) -> None:
        with self._lock:
            self._aggregates.ws_connections_total += 1

    def record_ws_disconnect(self) -> None:
        with self._lock:
            self._aggregates.ws_disconnections_total += 1

    def active_ws_connections(self) -> int:
        with self._lock:
            return max(
                0,
                self._aggregates.ws_connections_total - self._aggregates.ws_disconnections_total,
            )

    # ── lifecycle ────────────────────────────────────────────────────────
    def reset(self) -> None:
        with self._lock:
            self._aggregates = _Aggregates()

    def snapshot(self) -> BackendMetricsSnapshot:
        with self._lock:
            agg = self._aggregates
            avg = agg.total_duration_ms / agg.requests_total if agg.requests_total else 0.0
            return BackendMetricsSnapshot(
                requests_total=agg.requests_total,
                requests_in_flight=agg.requests_in_flight,
                requests_by_status=dict(agg.by_status),
                requests_by_method=dict(agg.by_method),
                average_duration_ms=avg,
                max_duration_ms=agg.max_duration_ms,
                api_errors_total=agg.api_errors_total,
                api_errors_by_code=dict(agg.by_error_code),
                ws_connections_total=agg.ws_connections_total,
                ws_disconnections_total=agg.ws_disconnections_total,
                ws_active_connections=max(
                    0,
                    agg.ws_connections_total - agg.ws_disconnections_total,
                ),
            )
