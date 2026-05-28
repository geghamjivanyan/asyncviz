"""Canonical asyncio.Semaphore instrumentation surface.

Public exports kept small + focused. Importers reach for
:class:`SemaphoreInstrumentationEngine` (the patcher) +
:func:`build_semaphore_diagnostics` (the diagnostics endpoint surface).
"""

from asyncviz.instrumentation.semaphore.semaphore_configuration import (
    DEFAULT_SEMAPHORE_CONFIG,
    SemaphoreInstrumentationConfig,
)
from asyncviz.instrumentation.semaphore.semaphore_diagnostics import (
    SemaphoreDiagnosticsSnapshot,
    build_semaphore_diagnostics,
)
from asyncviz.instrumentation.semaphore.semaphore_internal import (
    is_semaphore_internal,
    mark_semaphore_internal,
)
from asyncviz.instrumentation.semaphore.semaphore_metadata import (
    SemaphoreIdentity,
    SemaphoreKind,
    SemaphoreSnapshot,
)
from asyncviz.instrumentation.semaphore.semaphore_observability import (
    SemaphoreMetricsSnapshot,
    get_semaphore_metrics,
    reset_semaphore_metrics,
)
from asyncviz.instrumentation.semaphore.semaphore_patch import (
    PATCHED_CLASSES,
    SemaphoreInstrumentationEngine,
)
from asyncviz.instrumentation.semaphore.semaphore_registry import (
    SemaphoreRegistry,
    get_default_semaphore_registry,
    reset_default_semaphore_registry,
)
from asyncviz.instrumentation.semaphore.semaphore_state import (
    classify_semaphore,
    read_bound_value,
    read_initial_value,
    snapshot_semaphore,
)
from asyncviz.instrumentation.semaphore.semaphore_tracing import (
    SemaphoreTraceEntry,
    SemaphoreTraceKind,
    clear_semaphore_trace,
    get_semaphore_trace,
    is_semaphore_trace_enabled,
    record_semaphore_trace,
    set_semaphore_trace_enabled,
)

__all__ = [
    "DEFAULT_SEMAPHORE_CONFIG",
    "PATCHED_CLASSES",
    "SemaphoreDiagnosticsSnapshot",
    "SemaphoreIdentity",
    "SemaphoreInstrumentationConfig",
    "SemaphoreInstrumentationEngine",
    "SemaphoreKind",
    "SemaphoreMetricsSnapshot",
    "SemaphoreRegistry",
    "SemaphoreSnapshot",
    "SemaphoreTraceEntry",
    "SemaphoreTraceKind",
    "build_semaphore_diagnostics",
    "classify_semaphore",
    "clear_semaphore_trace",
    "get_default_semaphore_registry",
    "get_semaphore_metrics",
    "get_semaphore_trace",
    "is_semaphore_internal",
    "is_semaphore_trace_enabled",
    "mark_semaphore_internal",
    "read_bound_value",
    "read_initial_value",
    "record_semaphore_trace",
    "reset_default_semaphore_registry",
    "reset_semaphore_metrics",
    "set_semaphore_trace_enabled",
    "snapshot_semaphore",
]
