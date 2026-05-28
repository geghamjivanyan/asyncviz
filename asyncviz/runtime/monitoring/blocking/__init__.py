"""Blocking-threshold detection engine.

Sits between the lag monitor and the warning / event subsystems. Reads
classified lag measurements, applies escalation pressure and freeze-window
lifecycle, and emits replay-safe blocking events through the bus.

Layout:

* :mod:`blocking_classifier`    — lag severity → blocking severity.
* :mod:`blocking_thresholds`    — detector-side policy knobs.
* :mod:`blocking_escalation`    — consecutive-violation pressure → upgrade.
* :mod:`blocking_windows`       — open / extend / close freeze windows.
* :mod:`blocking_cooldown`      — per-severity dedup / suppression.
* :mod:`blocking_metrics`       — lifetime self-metrics.
* :mod:`blocking_statistics`    — lifetime window-level stats.
* :mod:`blocking_state`         — lifecycle state machine.
* :mod:`blocking_events`        — runtime-event factories.
* :mod:`blocking_observability` — public snapshot envelope.
* :mod:`blocking_diagnostics`   — debug-grade composite snapshot.
* :mod:`blocking_backpressure`  — bounded emit-rate self-protection.
* :mod:`blocking_tracing`       — opt-in debug ring.
* :mod:`blocking_configuration` — frozen knobs.
* :mod:`blocking_replay`        — replay helper.
* :mod:`blocking_detector`      — :class:`BlockingThresholdDetector`.
"""

from asyncviz.runtime.monitoring.blocking.blocking_backpressure import (
    BlockingBackpressureDecision,
    BlockingDetectorBackpressure,
)
from asyncviz.runtime.monitoring.blocking.blocking_classifier import (
    BlockingClassification,
    BlockingClassifier,
    BlockingSeverity,
)
from asyncviz.runtime.monitoring.blocking.blocking_configuration import (
    BlockingDetectorConfiguration,
)
from asyncviz.runtime.monitoring.blocking.blocking_cooldown import (
    BlockingCooldownPolicy,
    CooldownDecision,
)
from asyncviz.runtime.monitoring.blocking.blocking_detector import (
    BlockingThresholdDetector,
    DetectionListener,
    DetectionOutcome,
    EventEmitter,
)
from asyncviz.runtime.monitoring.blocking.blocking_diagnostics import (
    BlockingDiagnostics,
    BlockingDiagnosticsSnapshot,
)
from asyncviz.runtime.monitoring.blocking.blocking_escalation import (
    EscalationEngine,
    EscalationOutcome,
)
from asyncviz.runtime.monitoring.blocking.blocking_events import (
    BLOCKING_ESCALATION_EVENT_TYPE,
    BLOCKING_EVENT_TYPES,
    BLOCKING_VIOLATION_EVENT_TYPE,
    BLOCKING_WINDOW_CLOSED_EVENT_TYPE,
    BLOCKING_WINDOW_OPENED_EVENT_TYPE,
    build_blocking_escalation_event,
    build_blocking_violation_event,
    build_blocking_window_closed_event,
    build_blocking_window_opened_event,
)
from asyncviz.runtime.monitoring.blocking.blocking_metrics import (
    BlockingMetrics,
    BlockingMetricsSnapshot,
)
from asyncviz.runtime.monitoring.blocking.blocking_observability import BlockingSnapshot
from asyncviz.runtime.monitoring.blocking.blocking_replay import replay_into_detector
from asyncviz.runtime.monitoring.blocking.blocking_state import (
    BlockingDetectorLifecycle,
    BlockingDetectorState,
)
from asyncviz.runtime.monitoring.blocking.blocking_statistics import (
    BlockingStatistics,
    BlockingStatisticsSnapshot,
)
from asyncviz.runtime.monitoring.blocking.blocking_thresholds import BlockingThresholdPolicy
from asyncviz.runtime.monitoring.blocking.blocking_tracing import (
    BlockingTracer,
    BlockingTraceRecord,
)
from asyncviz.runtime.monitoring.blocking.blocking_windows import (
    BlockingWindowSnapshot,
    BlockingWindowTracker,
    WindowTransition,
)
from asyncviz.runtime.monitoring.blocking.stack_capture import (
    BLOCKING_STACK_CAPTURE_EVENT_TYPE,
    BlockingStackCaptureEngine,
    CapturedFrame,
    CapturedStack,
    CapturedTaskMetadata,
    StackCaptureConfiguration,
    StackCaptureDiagnosticsSnapshot,
    StackCaptureLimits,
    StackCaptureMetricsSnapshot,
    StackCaptureSnapshot,
    StackCaptureStatisticsSnapshot,
)

__all__ = [
    "BLOCKING_ESCALATION_EVENT_TYPE",
    "BLOCKING_EVENT_TYPES",
    "BLOCKING_STACK_CAPTURE_EVENT_TYPE",
    "BLOCKING_VIOLATION_EVENT_TYPE",
    "BLOCKING_WINDOW_CLOSED_EVENT_TYPE",
    "BLOCKING_WINDOW_OPENED_EVENT_TYPE",
    "BlockingBackpressureDecision",
    "BlockingClassification",
    "BlockingClassifier",
    "BlockingCooldownPolicy",
    "BlockingDetectorBackpressure",
    "BlockingDetectorConfiguration",
    "BlockingDetectorLifecycle",
    "BlockingDetectorState",
    "BlockingDiagnostics",
    "BlockingDiagnosticsSnapshot",
    "BlockingMetrics",
    "BlockingMetricsSnapshot",
    "BlockingSeverity",
    "BlockingSnapshot",
    "BlockingStackCaptureEngine",
    "BlockingStatistics",
    "BlockingStatisticsSnapshot",
    "BlockingThresholdDetector",
    "BlockingThresholdPolicy",
    "BlockingTraceRecord",
    "BlockingTracer",
    "BlockingWindowSnapshot",
    "BlockingWindowTracker",
    "CapturedFrame",
    "CapturedStack",
    "CapturedTaskMetadata",
    "CooldownDecision",
    "DetectionListener",
    "DetectionOutcome",
    "EscalationEngine",
    "EscalationOutcome",
    "EventEmitter",
    "StackCaptureConfiguration",
    "StackCaptureDiagnosticsSnapshot",
    "StackCaptureLimits",
    "StackCaptureMetricsSnapshot",
    "StackCaptureSnapshot",
    "StackCaptureStatisticsSnapshot",
    "WindowTransition",
    "build_blocking_escalation_event",
    "build_blocking_violation_event",
    "build_blocking_window_closed_event",
    "build_blocking_window_opened_event",
    "replay_into_detector",
]
