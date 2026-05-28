"""Canonical event-backpressure protection layer."""

from asyncviz.runtime.backpressure.adaptive_backpressure import (
    ActionListener,
    AdaptiveBackpressureController,
)
from asyncviz.runtime.backpressure.backpressure_budget import (
    BackpressureBudget,
    BudgetSnapshot,
)
from asyncviz.runtime.backpressure.backpressure_configuration import (
    BackpressureConfig,
    DropPolicy,
    EmergencyAction,
    default_config,
    lean_config,
    relaxed_config,
)
from asyncviz.runtime.backpressure.backpressure_diagnostics import (
    BackpressureDiagnostics,
    build_backpressure_diagnostics,
)
from asyncviz.runtime.backpressure.backpressure_integrity import (
    BackpressureIntegrityError,
    IntegrityViolation,
    check_drop_policy,
    check_pressure_ratio,
    check_state_transition,
)
from asyncviz.runtime.backpressure.backpressure_observability import (
    BackpressureMetricsSnapshot,
    get_backpressure_metrics,
    get_backpressure_metrics_snapshot,
    reset_backpressure_metrics,
)
from asyncviz.runtime.backpressure.backpressure_policy import (
    BackpressurePolicy,
    DefaultBackpressurePolicy,
)
from asyncviz.runtime.backpressure.backpressure_queue import (
    EnqueueVerdict,
    PriorityBoundedQueue,
    QueueStats,
)
from asyncviz.runtime.backpressure.backpressure_thresholds import (
    is_downgrade,
    is_upgrade,
    lower_band,
    state_for_ratio,
)
from asyncviz.runtime.backpressure.backpressure_tracing import (
    BackpressureTraceEntry,
    BackpressureTraceKind,
    clear_backpressure_trace,
    get_backpressure_trace,
    is_backpressure_trace_enabled,
    record_backpressure_trace,
    set_backpressure_trace_enabled,
)
from asyncviz.runtime.backpressure.bounded_event_channel import (
    BoundedEventChannel,
    ChannelStats,
)
from asyncviz.runtime.backpressure.event_backpressure_controller import (
    EventBackpressureController,
)
from asyncviz.runtime.backpressure.models.degradation_action import (
    ActionKind,
    DegradationAction,
)
from asyncviz.runtime.backpressure.models.overflow_marker import (
    OVERFLOW_MARKER_EVENT_TYPE,
    OverflowMarker,
)
from asyncviz.runtime.backpressure.models.overload_state import (
    OverloadSnapshot,
    OverloadState,
)
from asyncviz.runtime.backpressure.models.pressure_signal import (
    PressureSignal,
    PressureSource,
)
from asyncviz.runtime.backpressure.overload_detector import (
    OverloadDetector,
    StateTransitionListener,
)
from asyncviz.runtime.backpressure.reducer_backpressure import (
    ReducerBackpressureAdapter,
    ReducerBackpressureStats,
)
from asyncviz.runtime.backpressure.replay_backpressure import (
    ReplayBackpressureAdapter,
    ReplayBackpressureStats,
    overflow_marker_to_event,
)
from asyncviz.runtime.backpressure.topology_backpressure import (
    BoundedTopologyView,
    TopologyBackpressureStats,
)
from asyncviz.runtime.backpressure.utils.hysteresis import (
    ema_smooth,
    needs_downgrade,
    needs_upgrade,
)
from asyncviz.runtime.backpressure.websocket_backpressure import (
    SubscriberStats,
    WebsocketBackpressureRegistry,
    WebsocketSubscriberChannel,
    overflow_marker_for_subscriber,
)

__all__ = [
    "OVERFLOW_MARKER_EVENT_TYPE",
    "ActionKind",
    "ActionListener",
    "AdaptiveBackpressureController",
    "BackpressureBudget",
    "BackpressureConfig",
    "BackpressureDiagnostics",
    "BackpressureIntegrityError",
    "BackpressureMetricsSnapshot",
    "BackpressurePolicy",
    "BackpressureTraceEntry",
    "BackpressureTraceKind",
    "BoundedEventChannel",
    "BoundedTopologyView",
    "BudgetSnapshot",
    "ChannelStats",
    "DefaultBackpressurePolicy",
    "DegradationAction",
    "DropPolicy",
    "EmergencyAction",
    "EnqueueVerdict",
    "EventBackpressureController",
    "IntegrityViolation",
    "OverflowMarker",
    "OverloadDetector",
    "OverloadSnapshot",
    "OverloadState",
    "PressureSignal",
    "PressureSource",
    "PriorityBoundedQueue",
    "QueueStats",
    "ReducerBackpressureAdapter",
    "ReducerBackpressureStats",
    "ReplayBackpressureAdapter",
    "ReplayBackpressureStats",
    "StateTransitionListener",
    "SubscriberStats",
    "TopologyBackpressureStats",
    "WebsocketBackpressureRegistry",
    "WebsocketSubscriberChannel",
    "build_backpressure_diagnostics",
    "check_drop_policy",
    "check_pressure_ratio",
    "check_state_transition",
    "clear_backpressure_trace",
    "default_config",
    "ema_smooth",
    "get_backpressure_metrics",
    "get_backpressure_metrics_snapshot",
    "get_backpressure_trace",
    "is_backpressure_trace_enabled",
    "is_downgrade",
    "is_upgrade",
    "lean_config",
    "lower_band",
    "needs_downgrade",
    "needs_upgrade",
    "overflow_marker_for_subscriber",
    "overflow_marker_to_event",
    "record_backpressure_trace",
    "relaxed_config",
    "reset_backpressure_metrics",
    "set_backpressure_trace_enabled",
    "state_for_ratio",
]
