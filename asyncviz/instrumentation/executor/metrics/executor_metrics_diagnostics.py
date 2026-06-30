"""Diagnostics surface for the executor metrics engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from asyncviz.instrumentation.executor.metrics.executor_metrics_models import (
    ExecutorMetricsSnapshot,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_tracing import (
    ExecutorMetricsTraceEntry,
    get_executor_metrics_trace,
    is_executor_metrics_trace_enabled,
)


@dataclass(frozen=True, slots=True)
class ExecutorMetricsDiagnostics:
    snapshot: ExecutorMetricsSnapshot
    trace_enabled: bool
    trace_count: int
    recent_trace: tuple[ExecutorMetricsTraceEntry, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot": self.snapshot.to_dict(),
            "trace_enabled": self.trace_enabled,
            "trace_count": self.trace_count,
            "recent_trace": [
                {"kind": e.kind, "detail": e.detail, "at_monotonic": e.at_monotonic}
                for e in self.recent_trace
            ],
        }


def build_executor_metrics_diagnostics(
    snapshot: ExecutorMetricsSnapshot,
    *,
    tail: int = 16,
) -> ExecutorMetricsDiagnostics:
    trace = get_executor_metrics_trace()
    return ExecutorMetricsDiagnostics(
        snapshot=snapshot,
        trace_enabled=is_executor_metrics_trace_enabled(),
        trace_count=len(trace),
        recent_trace=trace[-tail:] if tail > 0 else trace,
    )
