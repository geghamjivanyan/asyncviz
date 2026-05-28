"""Canonical ``asyncio.gather`` instrumentation surface.

Public exports kept small + focused. Importers reach for
:class:`GatherInstrumentationEngine` (the patcher) +
:func:`build_gather_diagnostics` (the diagnostics endpoint surface).
"""

from asyncviz.instrumentation.gather.gather_configuration import (
    DEFAULT_GATHER_CONFIG,
    GatherInstrumentationConfig,
)
from asyncviz.instrumentation.gather.gather_diagnostics import (
    GatherDiagnosticsSnapshot,
    build_gather_diagnostics,
)
from asyncviz.instrumentation.gather.gather_internal import (
    is_internal_gather,
    suppress_gather_instrumentation,
)
from asyncviz.instrumentation.gather.gather_metadata import (
    GatherIdentity,
    GatherSnapshot,
)
from asyncviz.instrumentation.gather.gather_observability import (
    GatherMetricsSnapshot,
    get_gather_metrics,
    reset_gather_metrics,
)
from asyncviz.instrumentation.gather.gather_patch import (
    GatherInstrumentationEngine,
    TaskIdResolver,
)
from asyncviz.instrumentation.gather.gather_registry import (
    GatherRegistry,
    get_default_gather_registry,
    reset_default_gather_registry,
)
from asyncviz.instrumentation.gather.gather_tracing import (
    GatherTraceEntry,
    GatherTraceKind,
    clear_gather_trace,
    get_gather_trace,
    is_gather_trace_enabled,
    record_gather_trace,
    set_gather_trace_enabled,
)

__all__ = [
    "DEFAULT_GATHER_CONFIG",
    "GatherDiagnosticsSnapshot",
    "GatherIdentity",
    "GatherInstrumentationConfig",
    "GatherInstrumentationEngine",
    "GatherMetricsSnapshot",
    "GatherRegistry",
    "GatherSnapshot",
    "GatherTraceEntry",
    "GatherTraceKind",
    "TaskIdResolver",
    "build_gather_diagnostics",
    "clear_gather_trace",
    "get_default_gather_registry",
    "get_gather_metrics",
    "get_gather_trace",
    "is_gather_trace_enabled",
    "is_internal_gather",
    "record_gather_trace",
    "reset_default_gather_registry",
    "reset_gather_metrics",
    "set_gather_trace_enabled",
    "suppress_gather_instrumentation",
]
