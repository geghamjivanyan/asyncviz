from __future__ import annotations

from fastapi import Request, WebSocket

from asyncviz.config import AsyncVizConfig
from asyncviz.dashboard.frontend_serving import FrontendServingService
from asyncviz.dashboard.health import HealthService
from asyncviz.dashboard.snapshots import SnapshotService
from asyncviz.dashboard.state.backend import BackendAppState
from asyncviz.dashboard.state.backend_metrics import BackendMetrics
from asyncviz.dashboard.state.metrics_state import MetricsState
from asyncviz.dashboard.state.runtime_state import RuntimeState
from asyncviz.dashboard.websocket.manager import ConnectionManager
from asyncviz.dashboard.websocket.streaming import RuntimeStreamingEngine
from asyncviz.runtime.clock import RuntimeClock
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


def get_config(request: Request) -> AsyncVizConfig:
    return request.app.state.config


def get_runtime_state(request: Request) -> RuntimeState:
    return request.app.state.runtime_state


def get_runtime_clock(request: Request) -> RuntimeClock:
    return request.app.state.runtime_clock


def get_event_queue(request: Request) -> InternalEventQueue:
    return request.app.state.event_queue


def get_state_store(request: Request) -> RuntimeStateStore:
    return request.app.state.state_store


def get_state_store_ws(websocket: WebSocket) -> RuntimeStateStore:
    return websocket.app.state.state_store


def get_timeline_engine(request: Request) -> TimelineSegmentEngine:
    return request.app.state.timeline_engine


def get_metrics_aggregator(request: Request) -> RuntimeMetricsAggregator:
    return request.app.state.metrics_aggregator


def get_warning_manager(request: Request) -> RuntimeWarningManager:
    return request.app.state.warning_manager


def get_replay_buffer(request: Request) -> EventReplayBuffer:
    return request.app.state.replay_buffer


def get_backend_state(request: Request) -> BackendAppState:
    return request.app.state.backend


def get_backend_metrics(request: Request) -> BackendMetrics:
    return request.app.state.backend_metrics


def get_websocket_gateway(request: Request):
    """Return the :class:`WebSocketGateway` bound at app startup."""
    return request.app.state.websocket_gateway


def get_streaming_engine(request: Request) -> RuntimeStreamingEngine:
    """Return the :class:`RuntimeStreamingEngine` bound at app startup."""
    return request.app.state.streaming_engine


def get_snapshot_service(request: Request) -> SnapshotService:
    """Return the :class:`SnapshotService` bound at app startup."""
    return request.app.state.snapshot_service


def get_health_service(request: Request) -> HealthService:
    """Return the :class:`HealthService` bound at app startup."""
    return request.app.state.health_service


def get_frontend_serving(request: Request) -> FrontendServingService:
    """Return the :class:`FrontendServingService` bound at app startup."""
    return request.app.state.frontend_serving


def get_shutdown_coordinator(request: Request) -> RuntimeShutdownCoordinator:
    """Return the :class:`RuntimeShutdownCoordinator` bound at app startup."""
    return request.app.state.shutdown_coordinator


def get_metrics_state(request: Request) -> MetricsState:
    return request.app.state.metrics_state


def get_websocket_manager(request: Request) -> ConnectionManager:
    return request.app.state.websocket_manager


def get_websocket_manager_ws(websocket: WebSocket) -> ConnectionManager:
    return websocket.app.state.websocket_manager


def get_task_registry(request: Request) -> TaskRegistry:
    return request.app.state.task_registry


def get_task_registry_ws(websocket: WebSocket) -> TaskRegistry:
    return websocket.app.state.task_registry


def get_websocket_bridge_ws(websocket: WebSocket):
    return websocket.app.state.websocket_bridge


def get_lag_monitor(request: Request) -> EventLoopLagMonitor:
    """Return the :class:`EventLoopLagMonitor` bound at app startup."""
    return request.app.state.lag_monitor


def get_blocking_detector(request: Request) -> BlockingThresholdDetector:
    """Return the :class:`BlockingThresholdDetector` bound at app startup."""
    return request.app.state.blocking_detector


def get_stack_capture_engine(request: Request) -> BlockingStackCaptureEngine:
    """Return the :class:`BlockingStackCaptureEngine` bound at app startup."""
    return request.app.state.stack_capture_engine


def get_blocking_warning_emitter(request: Request) -> BlockingWarningEmitter:
    """Return the :class:`BlockingWarningEmitter` bound at app startup."""
    return request.app.state.blocking_warning_emitter
