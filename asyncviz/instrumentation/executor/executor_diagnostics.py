"""Composed diagnostics snapshot for executor instrumentation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from asyncviz.instrumentation.executor.executor_observability import (
    ExecutorMetricsSnapshot,
    get_executor_metrics,
)
from asyncviz.instrumentation.executor.executor_registry import (
    ExecutorRegistry,
    WorkItemRegistry,
    get_default_executor_registry,
    get_default_work_item_registry,
)
from asyncviz.instrumentation.executor.executor_tracing import (
    ExecutorTraceEntry,
    get_executor_trace,
    is_executor_trace_enabled,
)


@dataclass(frozen=True, slots=True)
class ExecutorDiagnosticsSnapshot:
    executor_registry_size: int
    executor_registry_finalized: int
    work_item_registry_size: int
    work_item_registry_finalized: int
    metrics: ExecutorMetricsSnapshot
    trace_enabled: bool
    trace_count: int
    recent_trace: tuple[ExecutorTraceEntry, ...]
    executors: tuple[dict[str, Any], ...]
    work_items: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "executor_registry_size": self.executor_registry_size,
            "executor_registry_finalized": self.executor_registry_finalized,
            "work_item_registry_size": self.work_item_registry_size,
            "work_item_registry_finalized": self.work_item_registry_finalized,
            "metrics": asdict(self.metrics),
            "trace_enabled": self.trace_enabled,
            "trace_count": self.trace_count,
            "recent_trace": [asdict(entry) for entry in self.recent_trace],
            "executors": list(self.executors),
            "work_items": list(self.work_items),
        }


def _executor_identity_to_dict(identity: object) -> dict[str, Any]:
    return {
        "executor_id": getattr(identity, "executor_id", None),
        "executor_kind": getattr(identity, "executor_kind", None),
        "max_workers": getattr(identity, "max_workers", None),
        "thread_name_prefix": getattr(identity, "thread_name_prefix", None),
        "creator_task_id": getattr(identity, "creator_task_id", None),
        "name": getattr(identity, "name", None),
    }


def _work_item_identity_to_dict(identity: object) -> dict[str, Any]:
    return {
        "work_item_id": getattr(identity, "work_item_id", None),
        "executor_id": getattr(identity, "executor_id", None),
        "submitting_task_id": getattr(identity, "submitting_task_id", None),
        "callable_name": getattr(identity, "callable_name", None),
    }


def build_executor_diagnostics(
    *,
    tail: int = 16,
    executor_registry: ExecutorRegistry | None = None,
    work_item_registry: WorkItemRegistry | None = None,
) -> ExecutorDiagnosticsSnapshot:
    exec_reg = executor_registry or get_default_executor_registry()
    work_reg = work_item_registry or get_default_work_item_registry()
    trace = get_executor_trace()
    return ExecutorDiagnosticsSnapshot(
        executor_registry_size=len(exec_reg),
        executor_registry_finalized=exec_reg.finalized_count,
        work_item_registry_size=len(work_reg),
        work_item_registry_finalized=work_reg.finalized_count,
        metrics=get_executor_metrics().snapshot(),
        trace_enabled=is_executor_trace_enabled(),
        trace_count=len(trace),
        recent_trace=trace[-tail:] if tail > 0 else trace,
        executors=tuple(
            _executor_identity_to_dict(identity) for identity in exec_reg.iter_identities()
        ),
        work_items=tuple(
            _work_item_identity_to_dict(identity) for identity in work_reg.iter_identities()
        ),
    )
