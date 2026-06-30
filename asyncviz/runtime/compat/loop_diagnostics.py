"""One-call loop-compatibility diagnostics builder."""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.compat.loop_adapter import AdapterStats
from asyncviz.runtime.compat.loop_clock_bridge import ClockDriftReport
from asyncviz.runtime.compat.loop_integrity import IntegrityFinding
from asyncviz.runtime.compat.loop_observability import (
    LoopCompatMetricsSnapshot,
)
from asyncviz.runtime.compat.loop_queue_bridge import QueueBridgeStats
from asyncviz.runtime.compat.loop_scheduler_bridge import SchedulerBridgeStats
from asyncviz.runtime.compat.loop_task_bridge import TaskBridgeStats
from asyncviz.runtime.compat.loop_tracing import LoopCompatTraceEntry, get_loop_compat_trace
from asyncviz.runtime.compat.models.loop_state import LoopState
from asyncviz.runtime.compat.replay_loop_bridge import ReplayLoopReport
from asyncviz.runtime.compat.websocket_loop_bridge import WebsocketBridgeReport


@dataclass(frozen=True, slots=True)
class LoopCompatDiagnostics:
    state: LoopState
    metrics: LoopCompatMetricsSnapshot
    adapter: AdapterStats
    clock: ClockDriftReport
    task: TaskBridgeStats
    queue: QueueBridgeStats
    scheduler: SchedulerBridgeStats
    replay: ReplayLoopReport
    websocket: WebsocketBridgeReport
    integrity_findings: tuple[IntegrityFinding, ...]
    trace: tuple[LoopCompatTraceEntry, ...]


@dataclass(frozen=True, slots=True)
class LoopCompatDiagnosticsInputs:
    state: LoopState
    metrics: LoopCompatMetricsSnapshot
    adapter: AdapterStats
    clock: ClockDriftReport
    task: TaskBridgeStats
    queue: QueueBridgeStats
    scheduler: SchedulerBridgeStats
    replay: ReplayLoopReport
    websocket: WebsocketBridgeReport
    integrity_findings: tuple[IntegrityFinding, ...] = ()
    trace_limit: int = 64


def build_loop_compat_diagnostics(
    inputs: LoopCompatDiagnosticsInputs,
) -> LoopCompatDiagnostics:
    trace = get_loop_compat_trace()
    if inputs.trace_limit > 0 and len(trace) > inputs.trace_limit:
        trace = trace[-inputs.trace_limit :]
    return LoopCompatDiagnostics(
        state=inputs.state,
        metrics=inputs.metrics,
        adapter=inputs.adapter,
        clock=inputs.clock,
        task=inputs.task,
        queue=inputs.queue,
        scheduler=inputs.scheduler,
        replay=inputs.replay,
        websocket=inputs.websocket,
        integrity_findings=inputs.integrity_findings,
        trace=trace,
    )
