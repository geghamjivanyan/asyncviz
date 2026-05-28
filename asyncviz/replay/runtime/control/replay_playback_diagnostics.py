"""Diagnostics builder for the playback coordination layer."""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.runtime.control.models.playback_phase import (
    PlaybackPhaseSnapshot,
)
from asyncviz.replay.runtime.control.replay_playback_backpressure import (
    CoordinationQueueStats,
)
from asyncviz.replay.runtime.control.replay_playback_observability import (
    PlaybackCoordinationMetricsSnapshot,
    get_coordination_metrics_snapshot,
)
from asyncviz.replay.runtime.control.replay_playback_tracing import (
    CoordinationTraceEntry,
    get_coordination_trace,
    is_coordination_trace_enabled,
)


@dataclass(frozen=True, slots=True)
class CoordinationDiagnostics:
    """Compact diagnostic view."""

    phase: PlaybackPhaseSnapshot
    metrics: PlaybackCoordinationMetricsSnapshot
    pause_queue: CoordinationQueueStats
    resume_queue: CoordinationQueueStats
    trace_enabled: bool
    recent_trace: tuple[CoordinationTraceEntry, ...]


def build_coordination_diagnostics(
    phase: PlaybackPhaseSnapshot,
    pause_queue: CoordinationQueueStats,
    resume_queue: CoordinationQueueStats,
    *,
    trace_limit: int = 32,
) -> CoordinationDiagnostics:
    trace = get_coordination_trace()
    if trace_limit > 0:
        trace = trace[-trace_limit:]
    return CoordinationDiagnostics(
        phase=phase,
        metrics=get_coordination_metrics_snapshot(),
        pause_queue=pause_queue,
        resume_queue=resume_queue,
        trace_enabled=is_coordination_trace_enabled(),
        recent_trace=trace,
    )
