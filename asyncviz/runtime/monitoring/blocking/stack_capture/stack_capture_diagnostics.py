"""Debug-grade composite snapshot for the stack-capture engine."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_backpressure import (
    StackCaptureBackpressure,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_configuration import (
    StackCaptureConfiguration,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_frames import (
    CapturedStack,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_metrics import (
    StackCaptureMetrics,
    StackCaptureMetricsSnapshot,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_statistics import (
    StackCaptureStatistics,
    StackCaptureStatisticsSnapshot,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_tracing import (
    StackCaptureTracer,
    StackCaptureTraceRecord,
)


@dataclass(frozen=True, slots=True)
class StackCaptureDiagnosticsSnapshot:
    state: str
    configuration: dict[str, object]
    statistics: StackCaptureStatisticsSnapshot
    metrics: StackCaptureMetricsSnapshot
    recent_captures: tuple[CapturedStack, ...]
    backpressure_pending: int
    backpressure_capacity: int
    backpressure_denied: int
    trace_enabled: bool
    trace_records: tuple[StackCaptureTraceRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "configuration": self.configuration,
            "statistics": self.statistics.to_dict(),
            "metrics": self.metrics.to_dict(),
            "recent_captures": [c.to_dict() for c in self.recent_captures],
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
                        "monotonic_ns": r.monotonic_ns,
                        "detail": r.detail,
                        "capture_id": r.capture_id,
                        "window_id": r.window_id,
                    }
                    for r in self.trace_records
                ],
            },
        }


class StackCaptureDiagnostics:
    """Composes the diagnostics snapshot from sub-engine borrows."""

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
        statistics: StackCaptureStatistics,
        metrics: StackCaptureMetrics,
        backpressure: StackCaptureBackpressure,
        tracer: StackCaptureTracer,
        state_getter: Callable[[], str],
        configuration_getter: Callable[[], StackCaptureConfiguration],
    ) -> None:
        self._statistics = statistics
        self._metrics = metrics
        self._backpressure = backpressure
        self._tracer = tracer
        self._state_getter = state_getter
        self._configuration_getter = configuration_getter

    def snapshot(self) -> StackCaptureDiagnosticsSnapshot:
        config = self._configuration_getter()
        return StackCaptureDiagnosticsSnapshot(
            state=self._state_getter(),
            configuration=config.to_dict(),
            statistics=self._statistics.snapshot(),
            metrics=self._metrics.snapshot(),
            recent_captures=self._statistics.recent(),
            backpressure_pending=self._backpressure.pending,
            backpressure_capacity=self._backpressure.capacity,
            backpressure_denied=self._backpressure.denied,
            trace_enabled=self._tracer.enabled,
            trace_records=self._tracer.snapshot(),
        )
