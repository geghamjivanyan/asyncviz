"""Canonical queue metrics engine surface.

Public API is small + focused: callers reach for
:class:`QueueMetricsEngine` (the aggregator) and
:func:`build_queue_metrics_diagnostics` (the diagnostics endpoint).
The richer types are re-exported here so adapters don't have to walk
into individual submodules.
"""

from asyncviz.instrumentation.queue.metrics.queue_metrics_backpressure import (
    is_at_capacity,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_configuration import (
    DEFAULT_QUEUE_METRICS_CONFIG,
    QueueMetricsConfig,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_diagnostics import (
    QueueMetricsDiagnostics,
    build_queue_metrics_diagnostics,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_engine import (
    DeltaListener,
    QueueMetricsEngine,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_models import (
    PressureLevel,
    QueueContentionSnapshot,
    QueueMetricsDelta,
    QueueMetricsEngineSelfSnapshot,
    QueueMetricsRecord,
    QueueMetricsSnapshot,
    QueueOccupancySnapshot,
    QueuePressureSnapshot,
    QueueThroughputSnapshot,
    QueueWaitSnapshot,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_observability import (
    get_queue_metrics_engine_metrics,
    reset_queue_metrics_engine_metrics,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_replay import (
    rebuild_metrics_from_events,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_serialization import (
    record_from_dict,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_tracing import (
    QueueMetricsTraceEntry,
    QueueMetricsTraceKind,
    clear_queue_metrics_trace,
    get_queue_metrics_trace,
    is_queue_metrics_trace_enabled,
    record_queue_metrics_trace,
    set_queue_metrics_trace_enabled,
)

__all__ = [
    "DEFAULT_QUEUE_METRICS_CONFIG",
    "DeltaListener",
    "PressureLevel",
    "QueueContentionSnapshot",
    "QueueMetricsConfig",
    "QueueMetricsDelta",
    "QueueMetricsDiagnostics",
    "QueueMetricsEngine",
    "QueueMetricsEngineSelfSnapshot",
    "QueueMetricsRecord",
    "QueueMetricsSnapshot",
    "QueueMetricsTraceEntry",
    "QueueMetricsTraceKind",
    "QueueOccupancySnapshot",
    "QueuePressureSnapshot",
    "QueueThroughputSnapshot",
    "QueueWaitSnapshot",
    "build_queue_metrics_diagnostics",
    "clear_queue_metrics_trace",
    "get_queue_metrics_engine_metrics",
    "get_queue_metrics_trace",
    "is_at_capacity",
    "is_queue_metrics_trace_enabled",
    "rebuild_metrics_from_events",
    "record_from_dict",
    "record_queue_metrics_trace",
    "reset_queue_metrics_engine_metrics",
    "set_queue_metrics_trace_enabled",
]
