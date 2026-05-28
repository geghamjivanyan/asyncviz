"""Diagnostics builder for the speed-coordination layer."""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.runtime.speed.models.speed_phase import SpeedPhaseSnapshot
from asyncviz.replay.runtime.speed.models.speed_profile import SpeedProfile
from asyncviz.replay.runtime.speed.models.speed_request import SpeedTransition
from asyncviz.replay.runtime.speed.replay_speed_backpressure import (
    SpeedQueueStats,
)
from asyncviz.replay.runtime.speed.replay_speed_clock import DriftSample
from asyncviz.replay.runtime.speed.replay_speed_observability import (
    SpeedMetricsSnapshot,
    get_speed_metrics_snapshot,
)
from asyncviz.replay.runtime.speed.replay_speed_tracing import (
    SpeedTraceEntry,
    get_speed_trace,
    is_speed_trace_enabled,
)


@dataclass(frozen=True, slots=True)
class SpeedDiagnostics:
    phase: SpeedPhaseSnapshot
    profile: SpeedProfile
    metrics: SpeedMetricsSnapshot
    queue: SpeedQueueStats
    last_drift_sample: DriftSample | None
    recent_history: tuple[SpeedTransition, ...]
    trace_enabled: bool
    recent_trace: tuple[SpeedTraceEntry, ...]


def build_speed_diagnostics(
    phase: SpeedPhaseSnapshot,
    profile: SpeedProfile,
    queue: SpeedQueueStats,
    history: tuple[SpeedTransition, ...],
    *,
    last_drift_sample: DriftSample | None = None,
    history_limit: int = 16,
    trace_limit: int = 32,
) -> SpeedDiagnostics:
    trace = get_speed_trace()
    if trace_limit > 0:
        trace = trace[-trace_limit:]
    return SpeedDiagnostics(
        phase=phase,
        profile=profile,
        metrics=get_speed_metrics_snapshot(),
        queue=queue,
        last_drift_sample=last_drift_sample,
        recent_history=history[-history_limit:],
        trace_enabled=is_speed_trace_enabled(),
        recent_trace=trace,
    )
