"""Diagnostic-surface adapter over the lag monitor's internals.

Splits "raw counters / state" (always available) from "trace ring"
(opt-in, debug only). The dashboard's diagnostics page consumes
:meth:`LagDiagnostics.snapshot` so it gets a stable, JSON-safe shape
regardless of which debug features are enabled.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from asyncviz.runtime.monitoring.event_loop.lag_backpressure import LagMonitorBackpressure
from asyncviz.runtime.monitoring.event_loop.lag_configuration import LagConfiguration
from asyncviz.runtime.monitoring.event_loop.lag_metrics import LagMetrics, LagMetricsSnapshot
from asyncviz.runtime.monitoring.event_loop.lag_state import LagMonitorState
from asyncviz.runtime.monitoring.event_loop.lag_statistics import (
    LagStatistics,
    LagStatisticsSnapshot,
)
from asyncviz.runtime.monitoring.event_loop.lag_tracing import LagTracer, LagTraceRecord


@dataclass(frozen=True, slots=True)
class LagDiagnosticsSnapshot:
    """Public diagnostics view; the wire shape served at /api/runtime/monitoring/lag/diagnostics."""

    state: LagMonitorState
    configuration: dict[str, object]
    statistics: LagStatisticsSnapshot
    metrics: LagMetricsSnapshot
    backpressure_pending: int
    backpressure_capacity: int
    backpressure_denied: int
    trace_enabled: bool
    trace_records: tuple[LagTraceRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "configuration": self.configuration,
            "statistics": self.statistics.to_dict(),
            "metrics": self.metrics.to_dict(),
            "backpressure": {
                "pending": self.backpressure_pending,
                "capacity": self.backpressure_capacity,
                "denied": self.backpressure_denied,
            },
            "trace": {
                "enabled": self.trace_enabled,
                "records": [
                    {
                        "kind": record.kind,
                        "sample_index": record.sample_index,
                        "monotonic_ns": record.monotonic_ns,
                        "detail": record.detail,
                        "lag_ns": record.lag_ns,
                    }
                    for record in self.trace_records
                ],
            },
        }


class LagDiagnostics:
    """Compose a :class:`LagDiagnosticsSnapshot` from monitor internals.

    Owns no state itself — every reference is a borrow from the
    :class:`EventLoopLagMonitor` that instantiates it. Constructed once
    per monitor and called on demand from the dashboard side.
    """

    __slots__ = (
        "_backpressure",
        "_configuration_getter",
        "_metrics",
        "_state_getter",
        "_statistics",
        "_tracer",
    )

    def __init__(
        self,
        *,
        statistics: LagStatistics,
        metrics: LagMetrics,
        backpressure: LagMonitorBackpressure,
        tracer: LagTracer,
        state_getter: Callable[[], LagMonitorState],
        configuration_getter: Callable[[], LagConfiguration],
    ) -> None:
        self._statistics = statistics
        self._metrics = metrics
        self._backpressure = backpressure
        self._tracer = tracer
        self._state_getter = state_getter
        self._configuration_getter = configuration_getter

    def snapshot(self) -> LagDiagnosticsSnapshot:
        config: LagConfiguration = self._configuration_getter()
        state: LagMonitorState = self._state_getter()
        return LagDiagnosticsSnapshot(
            state=state,
            configuration=config.to_dict(),
            statistics=self._statistics.snapshot(),
            metrics=self._metrics.snapshot(),
            backpressure_pending=self._backpressure.pending,
            backpressure_capacity=self._backpressure.capacity,
            backpressure_denied=self._backpressure.denied,
            trace_enabled=self._tracer.enabled,
            trace_records=self._tracer.snapshot(),
        )
