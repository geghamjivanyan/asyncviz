"""Debug-grade composite snapshot for the blocking detector.

Includes everything :class:`BlockingSnapshot` does plus the trace ring
and the backpressure counters. Served at
``/api/runtime/monitoring/blocking/diagnostics``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from asyncviz.runtime.monitoring.blocking.blocking_backpressure import (
    BlockingDetectorBackpressure,
)
from asyncviz.runtime.monitoring.blocking.blocking_configuration import (
    BlockingDetectorConfiguration,
)
from asyncviz.runtime.monitoring.blocking.blocking_metrics import (
    BlockingMetrics,
    BlockingMetricsSnapshot,
)
from asyncviz.runtime.monitoring.blocking.blocking_state import BlockingDetectorState
from asyncviz.runtime.monitoring.blocking.blocking_statistics import (
    BlockingStatistics,
    BlockingStatisticsSnapshot,
)
from asyncviz.runtime.monitoring.blocking.blocking_tracing import (
    BlockingTracer,
    BlockingTraceRecord,
)
from asyncviz.runtime.monitoring.blocking.blocking_windows import (
    BlockingWindowSnapshot,
    BlockingWindowTracker,
)


@dataclass(frozen=True, slots=True)
class BlockingDiagnosticsSnapshot:
    state: BlockingDetectorState
    configuration: dict[str, object]
    statistics: BlockingStatisticsSnapshot
    metrics: BlockingMetricsSnapshot
    active_window: BlockingWindowSnapshot | None
    recent_windows: tuple[BlockingWindowSnapshot, ...]
    backpressure_pending: int
    backpressure_capacity: int
    backpressure_denied: int
    trace_enabled: bool
    trace_records: tuple[BlockingTraceRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "configuration": self.configuration,
            "statistics": self.statistics.to_dict(),
            "metrics": self.metrics.to_dict(),
            "active_window": (
                self.active_window.to_dict() if self.active_window is not None else None
            ),
            "recent_windows": [w.to_dict() for w in self.recent_windows],
            "backpressure": {
                "pending": self.backpressure_pending,
                "capacity": self.backpressure_capacity,
                "denied": self.backpressure_denied,
            },
            "trace": {
                "enabled": self.trace_enabled,
                "records": [
                    {
                        "kind": r.kind,
                        "sample_index": r.sample_index,
                        "monotonic_ns": r.monotonic_ns,
                        "detail": r.detail,
                        "severity": r.severity,
                        "lag_ns": r.lag_ns,
                    }
                    for r in self.trace_records
                ],
            },
        }


class BlockingDiagnostics:
    """Composes a :class:`BlockingDiagnosticsSnapshot`. Owns no state."""

    __slots__ = (
        "_backpressure",
        "_configuration_getter",
        "_metrics",
        "_state_getter",
        "_statistics",
        "_tracer",
        "_windows",
    )

    def __init__(
        self,
        *,
        statistics: BlockingStatistics,
        metrics: BlockingMetrics,
        backpressure: BlockingDetectorBackpressure,
        tracer: BlockingTracer,
        windows: BlockingWindowTracker,
        state_getter: Callable[[], BlockingDetectorState],
        configuration_getter: Callable[[], BlockingDetectorConfiguration],
    ) -> None:
        self._statistics = statistics
        self._metrics = metrics
        self._backpressure = backpressure
        self._tracer = tracer
        self._windows = windows
        self._state_getter = state_getter
        self._configuration_getter = configuration_getter

    def snapshot(self) -> BlockingDiagnosticsSnapshot:
        config = self._configuration_getter()
        return BlockingDiagnosticsSnapshot(
            state=self._state_getter(),
            configuration=config.to_dict(),
            statistics=self._statistics.snapshot(),
            metrics=self._metrics.snapshot(),
            active_window=self._windows.active_snapshot(),
            recent_windows=self._windows.history_snapshot(),
            backpressure_pending=self._backpressure.pending,
            backpressure_capacity=self._backpressure.capacity,
            backpressure_denied=self._backpressure.denied,
            trace_enabled=self._tracer.enabled,
            trace_records=self._tracer.snapshot(),
        )
