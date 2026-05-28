"""Canonical ``run_in_executor`` instrumentation surface."""

from asyncviz.instrumentation.executor.executor_configuration import (
    DEFAULT_EXECUTOR_CONFIG,
    ExecutorInstrumentationConfig,
)
from asyncviz.instrumentation.executor.executor_diagnostics import (
    ExecutorDiagnosticsSnapshot,
    build_executor_diagnostics,
)
from asyncviz.instrumentation.executor.executor_internal import (
    is_internal_executor_call,
    suppress_executor_instrumentation,
)
from asyncviz.instrumentation.executor.executor_metadata import (
    ExecutorIdentity,
    ExecutorKind,
    WorkItemIdentity,
    WorkItemSnapshot,
)
from asyncviz.instrumentation.executor.executor_observability import (
    ExecutorMetricsSnapshot,
    get_executor_metrics,
    reset_executor_metrics,
)
from asyncviz.instrumentation.executor.executor_patch import (
    ExecutorInstrumentationEngine,
)
from asyncviz.instrumentation.executor.executor_registry import (
    ExecutorRegistry,
    WorkItemRegistry,
    get_default_executor_registry,
    get_default_work_item_registry,
    reset_default_executor_registry,
    reset_default_work_item_registry,
)
from asyncviz.instrumentation.executor.executor_state import (
    classify_executor,
    read_callable_name,
    read_max_workers,
    read_thread_name_prefix,
)
from asyncviz.instrumentation.executor.executor_tracing import (
    ExecutorTraceEntry,
    ExecutorTraceKind,
    clear_executor_trace,
    get_executor_trace,
    is_executor_trace_enabled,
    record_executor_trace,
    set_executor_trace_enabled,
)

__all__ = [
    "DEFAULT_EXECUTOR_CONFIG",
    "ExecutorDiagnosticsSnapshot",
    "ExecutorIdentity",
    "ExecutorInstrumentationConfig",
    "ExecutorInstrumentationEngine",
    "ExecutorKind",
    "ExecutorMetricsSnapshot",
    "ExecutorRegistry",
    "ExecutorTraceEntry",
    "ExecutorTraceKind",
    "WorkItemIdentity",
    "WorkItemRegistry",
    "WorkItemSnapshot",
    "build_executor_diagnostics",
    "classify_executor",
    "clear_executor_trace",
    "get_default_executor_registry",
    "get_default_work_item_registry",
    "get_executor_metrics",
    "get_executor_trace",
    "is_executor_trace_enabled",
    "is_internal_executor_call",
    "read_callable_name",
    "read_max_workers",
    "read_thread_name_prefix",
    "record_executor_trace",
    "reset_default_executor_registry",
    "reset_default_work_item_registry",
    "reset_executor_metrics",
    "set_executor_trace_enabled",
    "suppress_executor_instrumentation",
]
