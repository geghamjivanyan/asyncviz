"""Blocking warning emission engine.

The authoritative runtime-freeze warning pipeline. Subscribes to the
blocking detector + stack-capture engine, aggregates per-window
state into :class:`WarningGroup` lifecycles, and emits canonical
transition events through the bus.

Layout:

* :mod:`blocking_warning_state`         — lifecycle states + state guard.
* :mod:`blocking_warning_grouping`      — :class:`WarningGroup`
  aggregation + indexed registry.
* :mod:`blocking_warning_correlation`   — stack-capture → group lookup.
* :mod:`blocking_warning_policy`        — outcome → accept/reject gate.
* :mod:`blocking_warning_deduplication` — per-transition cooldowns.
* :mod:`blocking_warning_payloads`      — canonical wire payload.
* :mod:`blocking_warning_events`        — event type constants + factory.
* :mod:`blocking_warning_router`        — fan-out (bus + listeners).
* :mod:`blocking_warning_backpressure`  — bounded emit cap.
* :mod:`blocking_warning_metrics`       — engine self-counters.
* :mod:`blocking_warning_statistics`    — lifetime warning-content stats.
* :mod:`blocking_warning_tracing`       — opt-in debug ring.
* :mod:`blocking_warning_configuration` — frozen knobs.
* :mod:`blocking_warning_observability` — public snapshot.
* :mod:`blocking_warning_diagnostics`   — debug-grade composite snapshot.
* :mod:`blocking_warning_replay`        — replay + decode helpers.
* :mod:`blocking_warning_emitter`       —
  :class:`BlockingWarningEmitter` (the orchestrator).
"""

from asyncviz.runtime.warnings.blocking.blocking_warning_backpressure import (
    WarningBackpressureDecision,
    WarningEmitterBackpressure,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_configuration import (
    BlockingWarningConfiguration,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_correlation import (
    CaptureCorrelator,
    CorrelationResult,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_deduplication import (
    DEFAULT_ACTIVE_COOLDOWN_NS,
    DEFAULT_ESCALATED_COOLDOWN_NS,
    DEFAULT_EXPIRED_COOLDOWN_NS,
    DEFAULT_OPENED_COOLDOWN_NS,
    DEFAULT_RECOVERED_COOLDOWN_NS,
    DedupDecision,
    TransitionDeduplicator,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_diagnostics import (
    BlockingWarningDiagnostics,
    BlockingWarningDiagnosticsSnapshot,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_emitter import (
    BlockingWarningEmitter,
    ListenerCallback,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_events import (
    BLOCKING_WARNING_ACTIVE_EVENT_TYPE,
    BLOCKING_WARNING_ESCALATED_EVENT_TYPE,
    BLOCKING_WARNING_EVENT_TYPES,
    BLOCKING_WARNING_EXPIRED_EVENT_TYPE,
    BLOCKING_WARNING_OPENED_EVENT_TYPE,
    BLOCKING_WARNING_RECOVERED_EVENT_TYPE,
    build_blocking_warning_event,
    event_type_for_transition,
    is_blocking_warning_event,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_grouping import (
    EscalationEntry,
    WarningGroup,
    WarningGroupRegistry,
    WarningGroupSnapshot,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_metrics import (
    BlockingWarningMetrics,
    BlockingWarningMetricsSnapshot,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_observability import (
    BlockingWarningEmitterSnapshot,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_payloads import (
    BlockingWarningPayload,
    build_payload,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_policy import (
    BlockingWarningPolicy,
    PolicyDecision,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_replay import (
    decode_blocking_warning_event,
    replay_into_emitter,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_router import (
    EventEmitter,
    PayloadListener,
    RouterDispatchOutcome,
    WarningRouter,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_state import (
    BlockingWarningEmitterLifecycle,
    BlockingWarningEmitterState,
    BlockingWarningGroupState,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_statistics import (
    BlockingWarningStatistics,
    BlockingWarningStatisticsSnapshot,
    TopCoroutineStat,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_tracing import (
    BlockingWarningTracer,
    BlockingWarningTraceRecord,
)

__all__ = [
    "BLOCKING_WARNING_ACTIVE_EVENT_TYPE",
    "BLOCKING_WARNING_ESCALATED_EVENT_TYPE",
    "BLOCKING_WARNING_EVENT_TYPES",
    "BLOCKING_WARNING_EXPIRED_EVENT_TYPE",
    "BLOCKING_WARNING_OPENED_EVENT_TYPE",
    "BLOCKING_WARNING_RECOVERED_EVENT_TYPE",
    "DEFAULT_ACTIVE_COOLDOWN_NS",
    "DEFAULT_ESCALATED_COOLDOWN_NS",
    "DEFAULT_EXPIRED_COOLDOWN_NS",
    "DEFAULT_OPENED_COOLDOWN_NS",
    "DEFAULT_RECOVERED_COOLDOWN_NS",
    "BlockingWarningConfiguration",
    "BlockingWarningDiagnostics",
    "BlockingWarningDiagnosticsSnapshot",
    "BlockingWarningEmitter",
    "BlockingWarningEmitterLifecycle",
    "BlockingWarningEmitterSnapshot",
    "BlockingWarningEmitterState",
    "BlockingWarningGroupState",
    "BlockingWarningMetrics",
    "BlockingWarningMetricsSnapshot",
    "BlockingWarningPayload",
    "BlockingWarningPolicy",
    "BlockingWarningStatistics",
    "BlockingWarningStatisticsSnapshot",
    "BlockingWarningTraceRecord",
    "BlockingWarningTracer",
    "CaptureCorrelator",
    "CorrelationResult",
    "DedupDecision",
    "EscalationEntry",
    "EventEmitter",
    "ListenerCallback",
    "PayloadListener",
    "PolicyDecision",
    "RouterDispatchOutcome",
    "TopCoroutineStat",
    "TransitionDeduplicator",
    "WarningBackpressureDecision",
    "WarningEmitterBackpressure",
    "WarningGroup",
    "WarningGroupRegistry",
    "WarningGroupSnapshot",
    "WarningRouter",
    "build_blocking_warning_event",
    "build_payload",
    "decode_blocking_warning_event",
    "event_type_for_transition",
    "is_blocking_warning_event",
    "replay_into_emitter",
]
