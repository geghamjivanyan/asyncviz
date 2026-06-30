"""Engine diagnostics builder."""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.runtime.models.playback_state import PlaybackSnapshot
from asyncviz.replay.runtime.replay_observability import (
    ReplayEngineMetricsSnapshot,
    get_engine_metrics_snapshot,
)
from asyncviz.replay.runtime.replay_tracing import (
    ReplayEngineTraceEntry,
    get_engine_trace,
    is_engine_trace_enabled,
)


@dataclass(frozen=True, slots=True)
class ReplayEngineDiagnostics:
    """Compact view of the engine layer's runtime state."""

    playback: PlaybackSnapshot
    metrics: ReplayEngineMetricsSnapshot
    trace_enabled: bool
    recent_trace: tuple[ReplayEngineTraceEntry, ...]


def build_engine_diagnostics(
    playback: PlaybackSnapshot,
    *,
    trace_limit: int = 32,
) -> ReplayEngineDiagnostics:
    trace = get_engine_trace()
    if trace_limit > 0:
        trace = trace[-trace_limit:]
    return ReplayEngineDiagnostics(
        playback=playback,
        metrics=get_engine_metrics_snapshot(),
        trace_enabled=is_engine_trace_enabled(),
        recent_trace=trace,
    )
