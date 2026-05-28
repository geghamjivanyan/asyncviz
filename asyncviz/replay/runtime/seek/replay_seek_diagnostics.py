"""Diagnostics builder for the replay-seek layer."""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.runtime.seek.models.seek_state import SeekStateSnapshot
from asyncviz.replay.runtime.seek.replay_seek_backpressure import SeekQueueStats
from asyncviz.replay.runtime.seek.replay_seek_cache import SeekCacheStats
from asyncviz.replay.runtime.seek.replay_seek_observability import (
    SeekMetricsSnapshot,
    get_seek_metrics_snapshot,
)
from asyncviz.replay.runtime.seek.replay_seek_tracing import (
    SeekTraceEntry,
    get_seek_trace,
    is_seek_trace_enabled,
)


@dataclass(frozen=True, slots=True)
class SeekDiagnostics:
    state: SeekStateSnapshot
    metrics: SeekMetricsSnapshot
    cache: SeekCacheStats
    queue: SeekQueueStats
    trace_enabled: bool
    recent_trace: tuple[SeekTraceEntry, ...]


def build_seek_diagnostics(
    state: SeekStateSnapshot,
    cache: SeekCacheStats,
    queue: SeekQueueStats,
    *,
    trace_limit: int = 32,
) -> SeekDiagnostics:
    trace = get_seek_trace()
    if trace_limit > 0:
        trace = trace[-trace_limit:]
    return SeekDiagnostics(
        state=state,
        metrics=get_seek_metrics_snapshot(),
        cache=cache,
        queue=queue,
        trace_enabled=is_seek_trace_enabled(),
        recent_trace=trace,
    )
