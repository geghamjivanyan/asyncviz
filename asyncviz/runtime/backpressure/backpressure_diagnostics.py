"""Diagnostics builder for the backpressure layer."""

from __future__ import annotations

from dataclasses import dataclass, field

from asyncviz.runtime.backpressure.backpressure_observability import (
    BackpressureMetricsSnapshot,
    get_backpressure_metrics_snapshot,
)
from asyncviz.runtime.backpressure.backpressure_tracing import (
    BackpressureTraceEntry,
    get_backpressure_trace,
    is_backpressure_trace_enabled,
)
from asyncviz.runtime.backpressure.bounded_event_channel import ChannelStats
from asyncviz.runtime.backpressure.models.overload_state import (
    OverloadSnapshot,
)


@dataclass(frozen=True, slots=True)
class BackpressureDiagnostics:
    overload: OverloadSnapshot | None
    metrics: BackpressureMetricsSnapshot
    channels: tuple[ChannelStats, ...]
    trace_enabled: bool
    recent_trace: tuple[BackpressureTraceEntry, ...]
    notes: dict[str, str] = field(default_factory=dict)


def build_backpressure_diagnostics(
    *,
    overload: OverloadSnapshot | None = None,
    channels: tuple[ChannelStats, ...] = (),
    notes: dict[str, str] | None = None,
    trace_limit: int = 32,
) -> BackpressureDiagnostics:
    trace = get_backpressure_trace()
    if trace_limit > 0:
        trace = trace[-trace_limit:]
    return BackpressureDiagnostics(
        overload=overload,
        metrics=get_backpressure_metrics_snapshot(),
        channels=channels,
        trace_enabled=is_backpressure_trace_enabled(),
        recent_trace=trace,
        notes=dict(notes or {}),
    )
