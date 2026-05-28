"""Composed diagnostics snapshot for queue instrumentation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from asyncviz.instrumentation.queue.queue_observability import (
    QueueMetricsSnapshot,
    get_queue_metrics,
)
from asyncviz.instrumentation.queue.queue_registry import (
    QueueRegistry,
    get_default_queue_registry,
)
from asyncviz.instrumentation.queue.queue_tracing import (
    QueueTraceEntry,
    get_queue_trace,
    is_queue_trace_enabled,
)


@dataclass(frozen=True, slots=True)
class QueueDiagnosticsSnapshot:
    registry_size: int
    registry_finalized: int
    metrics: QueueMetricsSnapshot
    trace_enabled: bool
    trace_count: int
    recent_trace: tuple[QueueTraceEntry, ...]
    queues: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_size": self.registry_size,
            "registry_finalized": self.registry_finalized,
            "metrics": asdict(self.metrics),
            "trace_enabled": self.trace_enabled,
            "trace_count": self.trace_count,
            "recent_trace": [asdict(entry) for entry in self.recent_trace],
            "queues": list(self.queues),
        }


def _identity_to_dict(identity: object) -> dict[str, Any]:
    return {
        "queue_id": getattr(identity, "queue_id", None),
        "queue_kind": getattr(identity, "queue_kind", None),
        "maxsize": getattr(identity, "maxsize", None),
        "creator_task_id": getattr(identity, "creator_task_id", None),
        "name": getattr(identity, "name", None),
    }


def build_queue_diagnostics(
    *,
    tail: int = 16,
    registry: QueueRegistry | None = None,
) -> QueueDiagnosticsSnapshot:
    reg = registry or get_default_queue_registry()
    trace = get_queue_trace()
    return QueueDiagnosticsSnapshot(
        registry_size=len(reg),
        registry_finalized=reg.finalized_count,
        metrics=get_queue_metrics().snapshot(),
        trace_enabled=is_queue_trace_enabled(),
        trace_count=len(trace),
        recent_trace=trace[-tail:] if tail > 0 else trace,
        queues=tuple(_identity_to_dict(identity) for identity in reg.iter_identities()),
    )
