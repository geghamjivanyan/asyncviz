"""Diagnostics surface for the queue metrics engine.

Composes the engine's snapshot with the trace ring + the self-metrics
view into a single payload that the HTTP layer can render. Mirrors the
shape of :mod:`queue_diagnostics` so adapters can reuse layout code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from asyncviz.instrumentation.queue.metrics.queue_metrics_models import (
    QueueMetricsSnapshot,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_tracing import (
    QueueMetricsTraceEntry,
    get_queue_metrics_trace,
    is_queue_metrics_trace_enabled,
)


@dataclass(frozen=True, slots=True)
class QueueMetricsDiagnostics:
    snapshot: QueueMetricsSnapshot
    trace_enabled: bool
    trace_count: int
    recent_trace: tuple[QueueMetricsTraceEntry, ...] = field(default_factory=tuple)

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


def build_queue_metrics_diagnostics(
    snapshot: QueueMetricsSnapshot, *, tail: int = 16,
) -> QueueMetricsDiagnostics:
    trace = get_queue_metrics_trace()
    return QueueMetricsDiagnostics(
        snapshot=snapshot,
        trace_enabled=is_queue_metrics_trace_enabled(),
        trace_count=len(trace),
        recent_trace=trace[-tail:] if tail > 0 else trace,
    )
