"""Diagnostics builder for the replay loader layer."""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.loading.replay_observability import (
    ReplayLoaderMetricsSnapshot,
    get_loader_metrics_snapshot,
)
from asyncviz.replay.loading.replay_tracing import (
    ReplayTraceEntry,
    get_replay_trace,
    is_replay_trace_enabled,
)


@dataclass(frozen=True, slots=True)
class ReplayLoaderDiagnostics:
    """Compact view of the loader layer's runtime state."""

    metrics: ReplayLoaderMetricsSnapshot
    trace_enabled: bool
    recent_trace: tuple[ReplayTraceEntry, ...]


def build_loader_diagnostics(*, trace_limit: int = 32) -> ReplayLoaderDiagnostics:
    trace = get_replay_trace()
    if trace_limit > 0:
        trace = trace[-trace_limit:]
    return ReplayLoaderDiagnostics(
        metrics=get_loader_metrics_snapshot(),
        trace_enabled=is_replay_trace_enabled(),
        recent_trace=trace,
    )
