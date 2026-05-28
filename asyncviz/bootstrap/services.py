from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from fastapi import FastAPI

from asyncviz.config import AsyncVizConfig
from asyncviz.dashboard import create_app
from asyncviz.dashboard.frontend_serving import FrontendServingService
from asyncviz.dashboard.health import HealthService
from asyncviz.dashboard.snapshots import SnapshotService
from asyncviz.dashboard.state.metrics_state import MetricsState
from asyncviz.dashboard.state.runtime_state import RuntimeState
from asyncviz.dashboard.websocket.gateway import WebSocketGateway
from asyncviz.dashboard.websocket.manager import ConnectionManager
from asyncviz.dashboard.websocket.streaming import RuntimeStreamingEngine
from asyncviz.instrumentation.asyncio import AsyncioPatcher
from asyncviz.runtime.clock import RuntimeClock
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.metrics import RuntimeMetricsAggregator
from asyncviz.runtime.monitoring import (
    BlockingStackCaptureEngine,
    BlockingThresholdDetector,
    EventLoopLagMonitor,
)
from asyncviz.runtime.queue import InternalEventQueue
from asyncviz.runtime.replay import EventReplayBuffer
from asyncviz.runtime.shutdown import RuntimeShutdownCoordinator
from asyncviz.runtime.state import RuntimeStateStore
from asyncviz.runtime.tasks import TaskRegistry
from asyncviz.runtime.timeline import TimelineSegmentEngine
from asyncviz.runtime.warnings import RuntimeWarningManager
from asyncviz.runtime.warnings.blocking import BlockingWarningEmitter


@dataclass(slots=True)
class ServiceContainer:
    """All the dashboard's per-instance services in one struct.

    ``ServiceContainer.build`` is the single place where the FastAPI app and
    its sub-services are wired together. The bootstrap layer holds exactly
    one of these per running runtime.

    Future engines (event collector, timeline) will land here as additional
    fields — the bootstrap pipeline already knows how to construct and tear
    them down through this container.
    """

    app: FastAPI
    runtime_clock: RuntimeClock
    runtime_state: RuntimeState
    metrics_state: MetricsState
    websocket_manager: ConnectionManager
    websocket_gateway: WebSocketGateway
    event_bus: EventBus
    event_queue: InternalEventQueue
    task_registry: TaskRegistry
    state_store: RuntimeStateStore
    timeline_engine: TimelineSegmentEngine
    metrics_aggregator: RuntimeMetricsAggregator
    warning_manager: RuntimeWarningManager
    replay_buffer: EventReplayBuffer
    snapshot_service: SnapshotService
    streaming_engine: RuntimeStreamingEngine
    health_service: HealthService
    frontend_serving: FrontendServingService
    shutdown_coordinator: RuntimeShutdownCoordinator
    patcher: AsyncioPatcher
    lag_monitor: EventLoopLagMonitor
    blocking_detector: BlockingThresholdDetector
    stack_capture_engine: BlockingStackCaptureEngine
    blocking_warning_emitter: BlockingWarningEmitter

    @classmethod
    def build(cls, config: AsyncVizConfig) -> Self:
        app = create_app(config)
        return cls(
            app=app,
            runtime_clock=app.state.runtime_clock,
            runtime_state=app.state.runtime_state,
            metrics_state=app.state.metrics_state,
            websocket_manager=app.state.websocket_manager,
            websocket_gateway=app.state.websocket_gateway,
            event_bus=app.state.event_bus,
            event_queue=app.state.event_queue,
            task_registry=app.state.task_registry,
            state_store=app.state.state_store,
            timeline_engine=app.state.timeline_engine,
            metrics_aggregator=app.state.metrics_aggregator,
            warning_manager=app.state.warning_manager,
            replay_buffer=app.state.replay_buffer,
            snapshot_service=app.state.snapshot_service,
            streaming_engine=app.state.streaming_engine,
            health_service=app.state.health_service,
            frontend_serving=app.state.frontend_serving,
            shutdown_coordinator=app.state.shutdown_coordinator,
            patcher=app.state.patcher,
            lag_monitor=app.state.lag_monitor,
            blocking_detector=app.state.blocking_detector,
            stack_capture_engine=app.state.stack_capture_engine,
            blocking_warning_emitter=app.state.blocking_warning_emitter,
        )
