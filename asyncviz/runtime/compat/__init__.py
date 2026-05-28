"""Canonical alternate-event-loop compatibility layer."""

from asyncviz.runtime.compat.loop_adapter import AdapterStats, LoopAdapter
from asyncviz.runtime.compat.loop_clock_bridge import (
    ClockDriftReport,
    ClockSample,
    LoopClockBridge,
)
from asyncviz.runtime.compat.loop_configuration import (
    DEFAULT_CLOCK_DRIFT_TOLERANCE_NS,
    DEFAULT_PROBE_TIMEOUT_S,
    DEFAULT_TRACE_CAPACITY,
    LoopCompatConfig,
    LoopPreference,
    default_config,
    prefer_uvloop_config,
    strict_asyncio_config,
)
from asyncviz.runtime.compat.loop_diagnostics import (
    LoopCompatDiagnostics,
    LoopCompatDiagnosticsInputs,
    build_loop_compat_diagnostics,
)
from asyncviz.runtime.compat.loop_feature_detection import (
    detect_active_loop,
    is_running_under_uvloop,
    is_uvloop_available,
)
from asyncviz.runtime.compat.loop_integrity import (
    IntegrityFinding,
    IntegrityFindingKind,
    LoopIntegrityError,
    assert_compat_ok,
    check_capabilities,
)
from asyncviz.runtime.compat.loop_observability import (
    LoopCompatMetrics,
    LoopCompatMetricsSnapshot,
    get_loop_compat_metrics,
    get_loop_compat_metrics_snapshot,
    reset_loop_compat_metrics,
)
from asyncviz.runtime.compat.loop_policy_bridge import (
    LoopPolicyBridge,
    UvloopUnavailableError,
)
from asyncviz.runtime.compat.loop_queue_bridge import (
    LoopQueueBridge,
    QueueBridgeStats,
)
from asyncviz.runtime.compat.loop_scheduler_bridge import (
    LoopSchedulerBridge,
    SchedulerBridgeStats,
)
from asyncviz.runtime.compat.loop_task_bridge import (
    LoopTaskBridge,
    TaskBridgeStats,
    TaskFactory,
)
from asyncviz.runtime.compat.loop_tracing import (
    LoopCompatTraceEntry,
    LoopCompatTraceKind,
    clear_loop_compat_trace,
    get_loop_compat_trace,
    is_loop_compat_trace_enabled,
    loop_compat_trace_capacity,
    record_loop_compat_trace,
    set_loop_compat_trace_enabled,
)
from asyncviz.runtime.compat.models import (
    LoopCapabilities,
    LoopKind,
    LoopState,
    asyncio_baseline_capabilities,
    loop_kind_supports_replay,
    unknown_capabilities,
)
from asyncviz.runtime.compat.replay_loop_bridge import (
    ReplayLoopBridge,
    ReplayLoopReport,
)
from asyncviz.runtime.compat.uvloop_compat import (
    LoopCompatibilityManager,
    active_loop_kind,
    install_uvloop_if_available,
    is_uvloop_installed,
)
from asyncviz.runtime.compat.websocket_loop_bridge import (
    WebsocketBridgeReport,
    WebsocketLoopBridge,
)

__all__ = [
    "DEFAULT_CLOCK_DRIFT_TOLERANCE_NS",
    "DEFAULT_PROBE_TIMEOUT_S",
    "DEFAULT_TRACE_CAPACITY",
    "AdapterStats",
    "ClockDriftReport",
    "ClockSample",
    "IntegrityFinding",
    "IntegrityFindingKind",
    "LoopAdapter",
    "LoopCapabilities",
    "LoopClockBridge",
    "LoopCompatConfig",
    "LoopCompatDiagnostics",
    "LoopCompatDiagnosticsInputs",
    "LoopCompatMetrics",
    "LoopCompatMetricsSnapshot",
    "LoopCompatTraceEntry",
    "LoopCompatTraceKind",
    "LoopCompatibilityManager",
    "LoopIntegrityError",
    "LoopKind",
    "LoopPolicyBridge",
    "LoopPreference",
    "LoopQueueBridge",
    "LoopSchedulerBridge",
    "LoopState",
    "LoopTaskBridge",
    "QueueBridgeStats",
    "ReplayLoopBridge",
    "ReplayLoopReport",
    "SchedulerBridgeStats",
    "TaskBridgeStats",
    "TaskFactory",
    "UvloopUnavailableError",
    "WebsocketBridgeReport",
    "WebsocketLoopBridge",
    "active_loop_kind",
    "assert_compat_ok",
    "asyncio_baseline_capabilities",
    "build_loop_compat_diagnostics",
    "check_capabilities",
    "clear_loop_compat_trace",
    "default_config",
    "detect_active_loop",
    "get_loop_compat_metrics",
    "get_loop_compat_metrics_snapshot",
    "get_loop_compat_trace",
    "install_uvloop_if_available",
    "is_loop_compat_trace_enabled",
    "is_running_under_uvloop",
    "is_uvloop_available",
    "is_uvloop_installed",
    "loop_compat_trace_capacity",
    "loop_kind_supports_replay",
    "prefer_uvloop_config",
    "record_loop_compat_trace",
    "reset_loop_compat_metrics",
    "set_loop_compat_trace_enabled",
    "strict_asyncio_config",
    "unknown_capabilities",
]
