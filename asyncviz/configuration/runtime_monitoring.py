"""Runtime monitoring options.

Carries the user-facing knobs for the asyncio patcher + event-loop
lag detector. Cross-references the existing
:class:`asyncviz.runtime.monitoring.blocking.BlockingDetectorConfiguration`
defaults so the operator-facing options stay aligned with the
runtime's actual policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.configuration.runtime_defaults import (
    DEFAULT_CAPTURE_STACK_TRACES,
    DEFAULT_ENABLE_INSTRUMENTATION,
    DEFAULT_LAG_CRITICAL_MS,
    DEFAULT_LAG_FREEZE_MS,
    DEFAULT_LAG_SAMPLE_INTERVAL_MS,
    DEFAULT_LAG_WARNING_MS,
)


@dataclass(frozen=True, slots=True)
class MonitoringOptions:
    """Runtime instrumentation + lag-detection knobs."""

    enable_instrumentation: bool = DEFAULT_ENABLE_INSTRUMENTATION
    lag_warning_ms: float = DEFAULT_LAG_WARNING_MS
    lag_critical_ms: float = DEFAULT_LAG_CRITICAL_MS
    lag_freeze_ms: float = DEFAULT_LAG_FREEZE_MS
    lag_sample_interval_ms: float = DEFAULT_LAG_SAMPLE_INTERVAL_MS
    capture_stack_traces: bool = DEFAULT_CAPTURE_STACK_TRACES
