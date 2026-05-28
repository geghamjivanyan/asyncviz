"""Canonical runtime-failure-isolation layer."""

from asyncviz.runtime.resilience.circuit_breaker import (
    BreakerSnapshot,
    CircuitBreaker,
)
from asyncviz.runtime.resilience.degradation_policy import derive_runtime_mode
from asyncviz.runtime.resilience.failure_classifier import (
    classify_exception,
    classify_marker,
)
from asyncviz.runtime.resilience.failure_domain import (
    FailureDomain,
    FailureDomainSnapshot,
)
from asyncviz.runtime.resilience.isolation_backpressure import (
    BackpressureSuggestion,
    IsolationBackpressureBridge,
    SuggestionListener,
)
from asyncviz.runtime.resilience.isolation_configuration import (
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_FAILURE_WINDOW_S,
    DEFAULT_HALF_OPEN_PROBES,
    DEFAULT_MAX_RECOVERY_ATTEMPTS,
    DEFAULT_OPEN_DURATION_S,
    DEFAULT_RECOVERY_BACKOFF_S,
    DEFAULT_TRACE_CAPACITY,
    EmergencyMode,
    IsolationConfig,
    SubsystemPolicy,
    default_config,
    lean_config,
    relaxed_config,
)
from asyncviz.runtime.resilience.isolation_diagnostics import (
    IsolationDiagnostics,
    IsolationDiagnosticsInputs,
    build_isolation_diagnostics,
)
from asyncviz.runtime.resilience.isolation_integrity import (
    IntegrityFinding,
    IntegrityViolationKind,
    IsolationIntegrityError,
    assert_isolation_clean,
    check_domain,
    check_supervisor,
)
from asyncviz.runtime.resilience.isolation_observability import (
    IsolationMetrics,
    IsolationMetricsSnapshot,
    get_isolation_metrics,
    get_isolation_metrics_snapshot,
    reset_isolation_metrics,
)
from asyncviz.runtime.resilience.isolation_tracing import (
    IsolationTraceEntry,
    IsolationTraceKind,
    clear_isolation_trace,
    get_isolation_trace,
    is_isolation_trace_enabled,
    isolation_trace_capacity,
    record_isolation_trace,
    set_isolation_trace_enabled,
)
from asyncviz.runtime.resilience.models import (
    CORRUPTION_KINDS,
    CRITICAL_SUBSYSTEMS,
    DO_NOT_RETRY,
    BreakerState,
    FailureEvent,
    FailureKind,
    RecoveryOutcome,
    RecoveryVerdict,
    SubsystemId,
    admits_traffic,
    is_open,
)
from asyncviz.runtime.resilience.recorder_failure_isolation import (
    RecorderFailureIsolation,
)
from asyncviz.runtime.resilience.recovery_supervisor import (
    AsyncRecoveryHook,
    RecoverySupervisor,
    SupervisorSnapshot,
    SyncRecoveryHook,
)
from asyncviz.runtime.resilience.reducer_failure_isolation import (
    ReducerFailureIsolation,
)
from asyncviz.runtime.resilience.render_failure_isolation import (
    RenderFailureIsolation,
    RenderFallbackMode,
)
from asyncviz.runtime.resilience.replay_failure_isolation import (
    ReplayFailureIsolation,
)
from asyncviz.runtime.resilience.runtime_failure_manager import (
    ModeListener,
    RuntimeFailureManager,
)
from asyncviz.runtime.resilience.subsystem_boundary import (
    AsyncSubsystemBoundary,
    SubsystemBoundary,
    SubsystemUnavailable,
)
from asyncviz.runtime.resilience.websocket_failure_isolation import (
    WebsocketFailureIsolation,
)

__all__ = [
    "CORRUPTION_KINDS",
    "CRITICAL_SUBSYSTEMS",
    "DEFAULT_FAILURE_THRESHOLD",
    "DEFAULT_FAILURE_WINDOW_S",
    "DEFAULT_HALF_OPEN_PROBES",
    "DEFAULT_MAX_RECOVERY_ATTEMPTS",
    "DEFAULT_OPEN_DURATION_S",
    "DEFAULT_RECOVERY_BACKOFF_S",
    "DEFAULT_TRACE_CAPACITY",
    "DO_NOT_RETRY",
    "AsyncRecoveryHook",
    "AsyncSubsystemBoundary",
    "BackpressureSuggestion",
    "BreakerSnapshot",
    "BreakerState",
    "CircuitBreaker",
    "EmergencyMode",
    "FailureDomain",
    "FailureDomainSnapshot",
    "FailureEvent",
    "FailureKind",
    "IntegrityFinding",
    "IntegrityViolationKind",
    "IsolationBackpressureBridge",
    "IsolationConfig",
    "IsolationDiagnostics",
    "IsolationDiagnosticsInputs",
    "IsolationIntegrityError",
    "IsolationMetrics",
    "IsolationMetricsSnapshot",
    "IsolationTraceEntry",
    "IsolationTraceKind",
    "ModeListener",
    "RecorderFailureIsolation",
    "RecoveryOutcome",
    "RecoverySupervisor",
    "RecoveryVerdict",
    "ReducerFailureIsolation",
    "RenderFailureIsolation",
    "RenderFallbackMode",
    "ReplayFailureIsolation",
    "RuntimeFailureManager",
    "SubsystemBoundary",
    "SubsystemId",
    "SubsystemPolicy",
    "SubsystemUnavailable",
    "SuggestionListener",
    "SupervisorSnapshot",
    "SyncRecoveryHook",
    "WebsocketFailureIsolation",
    "admits_traffic",
    "assert_isolation_clean",
    "build_isolation_diagnostics",
    "check_domain",
    "check_supervisor",
    "classify_exception",
    "classify_marker",
    "clear_isolation_trace",
    "default_config",
    "derive_runtime_mode",
    "get_isolation_metrics",
    "get_isolation_metrics_snapshot",
    "get_isolation_trace",
    "is_isolation_trace_enabled",
    "is_open",
    "isolation_trace_capacity",
    "lean_config",
    "record_isolation_trace",
    "relaxed_config",
    "reset_isolation_metrics",
    "set_isolation_trace_enabled",
]
