"""Blocking stack-frame capture engine.

The runtime-freeze introspection layer. Reads :class:`DetectionOutcome`
from the blocking detector, decides (via policy) whether to walk the
Python frame stack, runs the walk through a filter chain, serializes
the result to a bounded JSON payload, and emits a replay-safe event.

Layout:

* :mod:`stack_capture_frames`        — :class:`CapturedFrame` /
  :class:`CapturedStack` / :class:`CapturedTaskMetadata` value types.
* :mod:`stack_capture_filters`       — module-prefix / filename
  internal-frame filter.
* :mod:`stack_capture_limits`        — depth / payload-size limits.
* :mod:`stack_capture_policy`        — capture decision policy.
* :mod:`stack_capture_sampler`       — frame providers + frame walker.
* :mod:`stack_capture_serializer`    — bounded JSON serializer.
* :mod:`stack_capture_context`       — re-entry guard + task enrichment.
* :mod:`stack_capture_backpressure`  — bounded emit cap.
* :mod:`stack_capture_metrics`       — lifetime engine counters.
* :mod:`stack_capture_statistics`    — lifetime capture-content stats.
* :mod:`stack_capture_events`        — event-type constant + factory.
* :mod:`stack_capture_tracing`       — opt-in debug ring.
* :mod:`stack_capture_observability` — public snapshot envelope.
* :mod:`stack_capture_diagnostics`   — debug-grade snapshot.
* :mod:`stack_capture_configuration` — frozen knobs.
* :mod:`stack_capture_replay`        — replay helpers.
* :mod:`stack_capture_engine`        —
  :class:`BlockingStackCaptureEngine` (the orchestrator).
"""

from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_backpressure import (
    StackCaptureBackpressure,
    StackCaptureBackpressureDecision,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_configuration import (
    StackCaptureConfiguration,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_context import (
    ReentryGuard,
    TaskMetadataResolver,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_diagnostics import (
    StackCaptureDiagnostics,
    StackCaptureDiagnosticsSnapshot,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_engine import (
    BlockingStackCaptureEngine,
    CaptureListener,
    EventEmitter,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_events import (
    BLOCKING_STACK_CAPTURE_EVENT_TYPE,
    STACK_CAPTURE_EVENT_TYPES,
    build_stack_capture_event,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_filters import (
    DEFAULT_INTERNAL_FILENAME_FRAGMENTS,
    DEFAULT_INTERNAL_MODULE_PREFIXES,
    FilterPolicy,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_frames import (
    CapturedFrame,
    CapturedStack,
    CapturedTaskMetadata,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_limits import (
    DEFAULT_MAX_CODE_LENGTH,
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_PAYLOAD_BYTES,
    StackCaptureLimits,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_metrics import (
    StackCaptureMetrics,
    StackCaptureMetricsSnapshot,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_observability import (
    StackCaptureSnapshot,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_policy import (
    CaptureDecision,
    StackCapturePolicy,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_replay import (
    decode_stack_capture_event,
    replay_into_engine,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_sampler import (
    FrameProvider,
    LiveFrameProvider,
    RawFrame,
    SampleOutcome,
    StackSampler,
    StaticFrameProvider,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_serializer import (
    SerializationOutcome,
    StackSerializer,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_statistics import (
    StackCaptureStatistics,
    StackCaptureStatisticsSnapshot,
    TopFrameStat,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_tracing import (
    StackCaptureTracer,
    StackCaptureTraceRecord,
)

__all__ = [
    "BLOCKING_STACK_CAPTURE_EVENT_TYPE",
    "DEFAULT_INTERNAL_FILENAME_FRAGMENTS",
    "DEFAULT_INTERNAL_MODULE_PREFIXES",
    "DEFAULT_MAX_CODE_LENGTH",
    "DEFAULT_MAX_DEPTH",
    "DEFAULT_MAX_PAYLOAD_BYTES",
    "STACK_CAPTURE_EVENT_TYPES",
    "BlockingStackCaptureEngine",
    "CaptureDecision",
    "CaptureListener",
    "CapturedFrame",
    "CapturedStack",
    "CapturedTaskMetadata",
    "EventEmitter",
    "FilterPolicy",
    "FrameProvider",
    "LiveFrameProvider",
    "RawFrame",
    "ReentryGuard",
    "SampleOutcome",
    "SerializationOutcome",
    "StackCaptureBackpressure",
    "StackCaptureBackpressureDecision",
    "StackCaptureConfiguration",
    "StackCaptureDiagnostics",
    "StackCaptureDiagnosticsSnapshot",
    "StackCaptureLimits",
    "StackCaptureMetrics",
    "StackCaptureMetricsSnapshot",
    "StackCapturePolicy",
    "StackCaptureSnapshot",
    "StackCaptureStatistics",
    "StackCaptureStatisticsSnapshot",
    "StackCaptureTraceRecord",
    "StackCaptureTracer",
    "StackSampler",
    "StackSerializer",
    "StaticFrameProvider",
    "TaskMetadataResolver",
    "TopFrameStat",
    "build_stack_capture_event",
    "decode_stack_capture_event",
    "replay_into_engine",
]
