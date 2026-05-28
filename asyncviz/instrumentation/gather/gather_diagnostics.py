"""Composed diagnostics snapshot for gather instrumentation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from asyncviz.instrumentation.gather.gather_observability import (
    GatherMetricsSnapshot,
    get_gather_metrics,
)
from asyncviz.instrumentation.gather.gather_registry import (
    GatherRegistry,
    get_default_gather_registry,
)
from asyncviz.instrumentation.gather.gather_tracing import (
    GatherTraceEntry,
    get_gather_trace,
    is_gather_trace_enabled,
)


@dataclass(frozen=True, slots=True)
class GatherDiagnosticsSnapshot:
    registry_size: int
    registry_finalized: int
    metrics: GatherMetricsSnapshot
    trace_enabled: bool
    trace_count: int
    recent_trace: tuple[GatherTraceEntry, ...]
    gathers: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_size": self.registry_size,
            "registry_finalized": self.registry_finalized,
            "metrics": asdict(self.metrics),
            "trace_enabled": self.trace_enabled,
            "trace_count": self.trace_count,
            "recent_trace": [asdict(entry) for entry in self.recent_trace],
            "gathers": list(self.gathers),
        }


def _identity_to_dict(identity: object) -> dict[str, Any]:
    return {
        "gather_id": getattr(identity, "gather_id", None),
        "parent_task_id": getattr(identity, "parent_task_id", None),
        "child_count": getattr(identity, "child_count", None),
        "child_task_ids": list(getattr(identity, "child_task_ids", ())),
        "return_exceptions": getattr(identity, "return_exceptions", None),
    }


def build_gather_diagnostics(
    *,
    tail: int = 16,
    registry: GatherRegistry | None = None,
) -> GatherDiagnosticsSnapshot:
    reg = registry or get_default_gather_registry()
    trace = get_gather_trace()
    return GatherDiagnosticsSnapshot(
        registry_size=len(reg),
        registry_finalized=reg.finalized_count,
        metrics=get_gather_metrics().snapshot(),
        trace_enabled=is_gather_trace_enabled(),
        trace_count=len(trace),
        recent_trace=trace[-tail:] if tail > 0 else trace,
        gathers=tuple(_identity_to_dict(identity) for identity in reg.iter_identities()),
    )
