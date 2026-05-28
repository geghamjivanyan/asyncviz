"""Runtime monitoring subsystem.

Production-grade, replay-aware monitoring layers that observe the runtime
without being part of its data path. Each child package owns one
diagnostic dimension:

* :mod:`event_loop` — lag sampling + statistics + threshold events.
* :mod:`blocking`   — blocking-violation classification, escalation,
  freeze-window lifecycle, cooldowns. Consumes lag-monitor output.

Public surface re-exports the canonical types from both child packages
so callers can write ``from asyncviz.runtime.monitoring import X``
without knowing which sub-package owns ``X``.
"""

from asyncviz.runtime.monitoring.blocking import (
    BLOCKING_ESCALATION_EVENT_TYPE,
    BLOCKING_EVENT_TYPES,
    BLOCKING_STACK_CAPTURE_EVENT_TYPE,
    BLOCKING_VIOLATION_EVENT_TYPE,
    BLOCKING_WINDOW_CLOSED_EVENT_TYPE,
    BLOCKING_WINDOW_OPENED_EVENT_TYPE,
    BlockingClassification,
    BlockingDetectorConfiguration,
    BlockingDetectorState,
    BlockingMetricsSnapshot,
    BlockingSeverity,
    BlockingSnapshot,
    BlockingStackCaptureEngine,
    BlockingStatisticsSnapshot,
    BlockingThresholdDetector,
    BlockingThresholdPolicy,
    BlockingWindowSnapshot,
    CapturedFrame,
    CapturedStack,
    CapturedTaskMetadata,
    DetectionOutcome,
    StackCaptureConfiguration,
    StackCaptureDiagnosticsSnapshot,
    StackCaptureLimits,
    StackCaptureMetricsSnapshot,
    StackCaptureSnapshot,
    StackCaptureStatisticsSnapshot,
)
from asyncviz.runtime.monitoring.event_loop import (
    EventLoopLagMonitor,
    LagConfiguration,
    LagMeasurement,
    LagMonitorObservability,
    LagMonitorState,
    LagSeverity,
    LagSnapshot,
    LagStatistics,
    LagThresholds,
)

__all__ = [
    "BLOCKING_ESCALATION_EVENT_TYPE",
    "BLOCKING_EVENT_TYPES",
    "BLOCKING_STACK_CAPTURE_EVENT_TYPE",
    "BLOCKING_VIOLATION_EVENT_TYPE",
    "BLOCKING_WINDOW_CLOSED_EVENT_TYPE",
    "BLOCKING_WINDOW_OPENED_EVENT_TYPE",
    "BlockingClassification",
    "BlockingDetectorConfiguration",
    "BlockingDetectorState",
    "BlockingMetricsSnapshot",
    "BlockingSeverity",
    "BlockingSnapshot",
    "BlockingStackCaptureEngine",
    "BlockingStatisticsSnapshot",
    "BlockingThresholdDetector",
    "BlockingThresholdPolicy",
    "BlockingWindowSnapshot",
    "CapturedFrame",
    "CapturedStack",
    "CapturedTaskMetadata",
    "DetectionOutcome",
    "EventLoopLagMonitor",
    "LagConfiguration",
    "LagMeasurement",
    "LagMonitorObservability",
    "LagMonitorState",
    "LagSeverity",
    "LagSnapshot",
    "LagStatistics",
    "LagThresholds",
    "StackCaptureConfiguration",
    "StackCaptureDiagnosticsSnapshot",
    "StackCaptureLimits",
    "StackCaptureMetricsSnapshot",
    "StackCaptureSnapshot",
    "StackCaptureStatisticsSnapshot",
]
