"""Diagnostics builder for the sampling layer."""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.sampling.adaptive_sampling import AdaptiveSnapshot
from asyncviz.runtime.sampling.sampling_budget import BudgetSnapshot
from asyncviz.runtime.sampling.sampling_observability import (
    SamplingMetricsSnapshot,
    get_sampling_metrics_snapshot,
)
from asyncviz.runtime.sampling.sampling_statistics import SamplingStatistics
from asyncviz.runtime.sampling.sampling_tracing import (
    SamplingTraceEntry,
    get_sampling_trace,
    is_sampling_trace_enabled,
)
from asyncviz.runtime.sampling.websocket_sampling import WebsocketSheddingStats


@dataclass(frozen=True, slots=True)
class SamplingDiagnostics:
    metrics: SamplingMetricsSnapshot
    budget: BudgetSnapshot | None
    statistics: SamplingStatistics | None
    adaptive: AdaptiveSnapshot | None
    websocket: WebsocketSheddingStats | None
    trace_enabled: bool
    recent_trace: tuple[SamplingTraceEntry, ...]


def build_sampling_diagnostics(
    *,
    budget: BudgetSnapshot | None = None,
    statistics: SamplingStatistics | None = None,
    adaptive: AdaptiveSnapshot | None = None,
    websocket: WebsocketSheddingStats | None = None,
    trace_limit: int = 32,
) -> SamplingDiagnostics:
    trace = get_sampling_trace()
    if trace_limit > 0:
        trace = trace[-trace_limit:]
    return SamplingDiagnostics(
        metrics=get_sampling_metrics_snapshot(),
        budget=budget,
        statistics=statistics,
        adaptive=adaptive,
        websocket=websocket,
        trace_enabled=is_sampling_trace_enabled(),
        recent_trace=trace,
    )
