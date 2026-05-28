"""Diagnostics builder for the memory-optimization layer."""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.memory.event_interning import InternerStats
from asyncviz.runtime.memory.event_pooling import PoolStats
from asyncviz.runtime.memory.memory_observability import (
    MemoryMetricsSnapshot,
    get_memory_metrics_snapshot,
)
from asyncviz.runtime.memory.memory_tracing import (
    MemoryTraceEntry,
    get_memory_trace,
    is_memory_trace_enabled,
)
from asyncviz.runtime.memory.topology_memory import TopologyStats
from asyncviz.runtime.memory.websocket_memory import WebsocketBufferStats


@dataclass(frozen=True, slots=True)
class MemoryDiagnostics:
    metrics: MemoryMetricsSnapshot
    interner: InternerStats | None
    pools: tuple[tuple[str, PoolStats], ...]
    topology: TopologyStats | None
    websocket_buffers: WebsocketBufferStats | None
    trace_enabled: bool
    recent_trace: tuple[MemoryTraceEntry, ...]


def build_memory_diagnostics(
    *,
    interner_stats: InternerStats | None = None,
    pools: tuple[tuple[str, PoolStats], ...] = (),
    topology_stats: TopologyStats | None = None,
    websocket_stats: WebsocketBufferStats | None = None,
    trace_limit: int = 32,
) -> MemoryDiagnostics:
    trace = get_memory_trace()
    if trace_limit > 0:
        trace = trace[-trace_limit:]
    return MemoryDiagnostics(
        metrics=get_memory_metrics_snapshot(),
        interner=interner_stats,
        pools=pools,
        topology=topology_stats,
        websocket_buffers=websocket_stats,
        trace_enabled=is_memory_trace_enabled(),
        recent_trace=trace,
    )
