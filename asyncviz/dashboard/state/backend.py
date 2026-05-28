"""Typed backend application-state container.

Centralizes references to every runtime-owned service so handlers /
middleware don't reach into the loosely-typed ``app.state`` dict
themselves. The instance lives at ``app.state.backend``; per-service
references stay at their existing ``app.state.X`` locations for
backward compatibility, but new code should prefer this typed view.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from asyncviz.config import AsyncVizConfig
    from asyncviz.dashboard.frontend_serving import FrontendServingService
    from asyncviz.dashboard.health import HealthService
    from asyncviz.dashboard.snapshots import SnapshotService
    from asyncviz.dashboard.state.backend_metrics import BackendMetrics
    from asyncviz.dashboard.state.metrics_state import MetricsState
    from asyncviz.dashboard.state.runtime_state import RuntimeState
    from asyncviz.dashboard.websocket.bridge import WebSocketBridge
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
class BackendAppState:
    """The dashboard's typed application state.

    Holds one reference per runtime-owned service plus the backend's own
    observability counters (:class:`BackendMetrics`). Bound to the FastAPI
    app at ``app.state.backend`` during :func:`create_app`.
    """

    config: AsyncVizConfig
    runtime_clock: RuntimeClock
    runtime_state: RuntimeState
    metrics_state: MetricsState
    metrics: BackendMetrics
    websocket_manager: ConnectionManager
    websocket_bridge: WebSocketBridge
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
    patcher: AsyncioPatcher
    lag_monitor: EventLoopLagMonitor
    blocking_detector: BlockingThresholdDetector
    stack_capture_engine: BlockingStackCaptureEngine
    blocking_warning_emitter: BlockingWarningEmitter
    #: Populated after :class:`BackendAppState` is constructed because
    #: the health service depends on the assembled container itself.
    health_service: HealthService | None = None
    #: Populated after :class:`BackendAppState` is constructed because
    #: the frontend serving service is mounted after the rest of the
    #: app is wired (router order matters).
    frontend_serving: FrontendServingService | None = None
    #: Populated after :class:`BackendAppState` is constructed because
    #: the shutdown coordinator captures every other service reference
    #: through this container.
    shutdown_coordinator: RuntimeShutdownCoordinator | None = None
    started: bool = False
    extras: dict[str, object] = field(default_factory=dict)
