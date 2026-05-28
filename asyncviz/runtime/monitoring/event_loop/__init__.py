"""Event-loop lag monitoring engine.

The canonical runtime-latency detection layer for AsyncViz. Layout:

* :mod:`lag_clock`           — monotonic-clock adapter (deterministic / fake).
* :mod:`lag_measurement`     — measurement value type + scheduler-delay math.
* :mod:`lag_thresholds`      — warning / critical / freeze threshold policy.
* :mod:`lag_configuration`   — runtime-tunable knobs (interval, thresholds).
* :mod:`lag_statistics`      — rolling-window aggregator (avg / p95 / p99).
* :mod:`lag_metrics`         — lifetime counters + self-observability.
* :mod:`lag_state`           — monitor lifecycle state machine.
* :mod:`lag_events`          — replay-safe event factories for the bus.
* :mod:`lag_sampler`         — single low-allocation sample callable.
* :mod:`lag_scheduler`       — asyncio cadence loop with drift correction.
* :mod:`lag_backpressure`    — sample dropping + self-protection policy.
* :mod:`lag_observability`   — public snapshot envelope.
* :mod:`lag_diagnostics`     — debug hooks, tracing, scheduler diagnostics.
* :mod:`lag_tracing`         — opt-in trace sink (debug-only).
* :mod:`lag_monitor`         — :class:`EventLoopLagMonitor` (the orchestrator).
"""

from asyncviz.runtime.monitoring.event_loop.lag_clock import (
    LagClock,
    MonotonicClockProtocol,
    SystemMonotonicClock,
)
from asyncviz.runtime.monitoring.event_loop.lag_configuration import (
    DEFAULT_CRITICAL_LAG_SECONDS,
    DEFAULT_FREEZE_LAG_SECONDS,
    DEFAULT_SAMPLE_INTERVAL_SECONDS,
    DEFAULT_STATISTICS_WINDOW,
    DEFAULT_WARNING_LAG_SECONDS,
    LagConfiguration,
)
from asyncviz.runtime.monitoring.event_loop.lag_diagnostics import (
    LagDiagnostics,
    LagDiagnosticsSnapshot,
)
from asyncviz.runtime.monitoring.event_loop.lag_events import (
    LAG_MEASUREMENT_EVENT_TYPE,
    LAG_THRESHOLD_BREACH_EVENT_TYPE,
    build_lag_measurement_event,
    build_lag_threshold_breach_event,
)
from asyncviz.runtime.monitoring.event_loop.lag_measurement import (
    LagMeasurement,
    calculate_lag,
)
from asyncviz.runtime.monitoring.event_loop.lag_metrics import LagMetrics, LagMetricsSnapshot
from asyncviz.runtime.monitoring.event_loop.lag_monitor import EventLoopLagMonitor
from asyncviz.runtime.monitoring.event_loop.lag_observability import LagSnapshot
from asyncviz.runtime.monitoring.event_loop.lag_state import LagMonitorState
from asyncviz.runtime.monitoring.event_loop.lag_statistics import (
    LagStatistics,
    LagStatisticsSnapshot,
)
from asyncviz.runtime.monitoring.event_loop.lag_thresholds import (
    LagSeverity,
    LagThresholdEvaluation,
    LagThresholds,
)
from asyncviz.runtime.monitoring.event_loop.lag_tracing import LagTracer, LagTraceRecord

__all__ = [
    "DEFAULT_CRITICAL_LAG_SECONDS",
    "DEFAULT_FREEZE_LAG_SECONDS",
    "DEFAULT_SAMPLE_INTERVAL_SECONDS",
    "DEFAULT_STATISTICS_WINDOW",
    "DEFAULT_WARNING_LAG_SECONDS",
    "LAG_MEASUREMENT_EVENT_TYPE",
    "LAG_THRESHOLD_BREACH_EVENT_TYPE",
    "EventLoopLagMonitor",
    "LagClock",
    "LagConfiguration",
    "LagDiagnostics",
    "LagDiagnosticsSnapshot",
    "LagMeasurement",
    "LagMetrics",
    "LagMetricsSnapshot",
    "LagMonitorObservability",
    "LagMonitorState",
    "LagSeverity",
    "LagSnapshot",
    "LagStatistics",
    "LagStatisticsSnapshot",
    "LagThresholdEvaluation",
    "LagThresholds",
    "LagTraceRecord",
    "LagTracer",
    "MonotonicClockProtocol",
    "SystemMonotonicClock",
    "build_lag_measurement_event",
    "build_lag_threshold_breach_event",
    "calculate_lag",
]


# Re-export under the canonical observability alias to satisfy upstream
# import paths that prefer the "Observability" suffix for snapshot types.
LagMonitorObservability = LagSnapshot
