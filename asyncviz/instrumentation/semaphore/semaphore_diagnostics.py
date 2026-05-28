"""Composed diagnostics snapshot for semaphore instrumentation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from asyncviz.instrumentation.semaphore.semaphore_observability import (
    SemaphoreMetricsSnapshot,
    get_semaphore_metrics,
)
from asyncviz.instrumentation.semaphore.semaphore_registry import (
    SemaphoreRegistry,
    get_default_semaphore_registry,
)
from asyncviz.instrumentation.semaphore.semaphore_tracing import (
    SemaphoreTraceEntry,
    get_semaphore_trace,
    is_semaphore_trace_enabled,
)


@dataclass(frozen=True, slots=True)
class SemaphoreDiagnosticsSnapshot:
    registry_size: int
    registry_finalized: int
    metrics: SemaphoreMetricsSnapshot
    trace_enabled: bool
    trace_count: int
    recent_trace: tuple[SemaphoreTraceEntry, ...]
    semaphores: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_size": self.registry_size,
            "registry_finalized": self.registry_finalized,
            "metrics": asdict(self.metrics),
            "trace_enabled": self.trace_enabled,
            "trace_count": self.trace_count,
            "recent_trace": [asdict(entry) for entry in self.recent_trace],
            "semaphores": list(self.semaphores),
        }


def _identity_to_dict(identity: object) -> dict[str, Any]:
    return {
        "semaphore_id": getattr(identity, "semaphore_id", None),
        "semaphore_kind": getattr(identity, "semaphore_kind", None),
        "initial_value": getattr(identity, "initial_value", None),
        "bound_value": getattr(identity, "bound_value", None),
        "creator_task_id": getattr(identity, "creator_task_id", None),
        "name": getattr(identity, "name", None),
    }


def build_semaphore_diagnostics(
    *,
    tail: int = 16,
    registry: SemaphoreRegistry | None = None,
) -> SemaphoreDiagnosticsSnapshot:
    reg = registry or get_default_semaphore_registry()
    trace = get_semaphore_trace()
    return SemaphoreDiagnosticsSnapshot(
        registry_size=len(reg),
        registry_finalized=reg.finalized_count,
        metrics=get_semaphore_metrics().snapshot(),
        trace_enabled=is_semaphore_trace_enabled(),
        trace_count=len(trace),
        recent_trace=trace[-tail:] if tail > 0 else trace,
        semaphores=tuple(_identity_to_dict(identity) for identity in reg.iter_identities()),
    )
