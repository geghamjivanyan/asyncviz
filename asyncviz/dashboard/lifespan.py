from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI

from asyncviz.config import AsyncVizConfig
from asyncviz.dashboard.state.metrics_state import MetricsState
from asyncviz.dashboard.state.runtime_state import RuntimeState
from asyncviz.dashboard.websocket.bridge import WebSocketBridge
from asyncviz.dashboard.websocket.manager import ConnectionManager
from asyncviz.dashboard.websocket.protocol import heartbeat
from asyncviz.dashboard.websocket.streaming import RuntimeStreamingEngine
from asyncviz.instrumentation.asyncio import AsyncioPatcher
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
from asyncviz.runtime.state import RuntimeStateStore, bind_store_to_event_bus
from asyncviz.runtime.tasks import TaskRegistry
from asyncviz.runtime.timeline import TimelineSegmentEngine
from asyncviz.runtime.warnings import RuntimeWarningManager
from asyncviz.runtime.warnings.blocking import BlockingWarningEmitter
from asyncviz.utils.logging import get_logger

#: Used in the fallback bus-only path (tests + scripts without an event
#: queue). The dashboard's normal path drives the store from the bridge's
#: queue post-dispatch hook so transitions carry the wire sequence.
_USE_BUS_BINDING_WHEN_NO_QUEUE = True

logger = get_logger("dashboard.lifespan")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Bring the runtime up; on exit, delegate teardown to the shutdown coordinator.

    The startup half of the lifespan still lives here because it is
    inherently sequential and order-sensitive (queue before bus, bridge
    before streaming, etc.). The shutdown half is centralized in
    :class:`RuntimeShutdownCoordinator` so every entrypoint —
    test-client lifespan exit, ``asyncviz.stop()``, SIGTERM — runs the
    exact same teardown sequence.
    """
    runtime_state: RuntimeState = app.state.runtime_state
    manager: ConnectionManager = app.state.websocket_manager
    metrics: MetricsState = app.state.metrics_state
    config: AsyncVizConfig = app.state.config
    event_bus: EventBus = app.state.event_bus
    event_queue: InternalEventQueue = app.state.event_queue
    task_registry: TaskRegistry = app.state.task_registry
    state_store: RuntimeStateStore = app.state.state_store
    timeline_engine: TimelineSegmentEngine = app.state.timeline_engine
    metrics_aggregator: RuntimeMetricsAggregator = app.state.metrics_aggregator
    warning_manager: RuntimeWarningManager = app.state.warning_manager
    replay_buffer: EventReplayBuffer = app.state.replay_buffer
    streaming_engine: RuntimeStreamingEngine = app.state.streaming_engine
    patcher: AsyncioPatcher = app.state.patcher
    lag_monitor: EventLoopLagMonitor = app.state.lag_monitor
    blocking_detector: BlockingThresholdDetector = app.state.blocking_detector
    stack_capture_engine: BlockingStackCaptureEngine = app.state.stack_capture_engine
    blocking_warning_emitter: BlockingWarningEmitter = app.state.blocking_warning_emitter
    coordinator: RuntimeShutdownCoordinator = app.state.shutdown_coordinator

    # Publish the dashboard's event loop reference so out-of-process
    # consumers (the replay CLI launcher, future programmatic
    # callers) can hop onto it via ``run_coroutine_threadsafe`` without
    # reading private state. Cleared in the shutdown coordinator.
    app.state.dashboard_loop = asyncio.get_running_loop()

    runtime_state.mark_started()
    await task_registry.start()
    # The queue MUST start before the bus — once running, the bus delegates
    # to it for every publish. The queue owns the dispatch loop.
    await event_queue.start()
    await event_bus.start()

    # Bus → store feedback loop is no longer wired here. The websocket bridge
    # is the queue's post-dispatch hook in this configuration, and *it* drives
    # the store via ``apply_queued`` so the store sees the queue-allocated
    # sequence on every event. This keeps per-task transition history
    # sequence-accurate. The bus subscription path exists only for
    # bridge-less / queue-less setups (legacy tests).
    state_store_subscription = None
    if _USE_BUS_BINDING_WHEN_NO_QUEUE and not event_queue.is_running:
        state_store_subscription = bind_store_to_event_bus(state_store, event_bus)

    # Timeline engine subscribes to state-store StateChange notifications. The
    # subscription must live across the lifespan so the engine sees every
    # transition the store applies; we tear it down before teardown so
    # disconnect cancellations don't fire stale segments.
    timeline_subscription = timeline_engine.bind(state_store)
    metrics_subscription = metrics_aggregator.bind(state_store)
    warning_subscription = warning_manager.bind(state_store)
    replay_subscription = replay_buffer.bind(state_store)

    bridge: WebSocketBridge = app.state.websocket_bridge
    await bridge.start()

    # Streaming engine: subscribes the runtime delta sources (metrics,
    # warnings, timeline) onto the websocket fanout. Must come up AFTER
    # the bridge so the connection manager is ready to broadcast.
    streaming_engine.start(loop=asyncio.get_running_loop())

    if config.enable_instrumentation:
        patcher.patch()
        queue_patcher = getattr(app.state, "queue_patcher", None)
        if queue_patcher is not None:
            queue_patcher.patch()
        semaphore_patcher = getattr(app.state, "semaphore_patcher", None)
        if semaphore_patcher is not None:
            semaphore_patcher.patch()
        gather_patcher = getattr(app.state, "gather_patcher", None)
        if gather_patcher is not None:
            gather_patcher.patch()
        executor_patcher = getattr(app.state, "executor_patcher", None)
        if executor_patcher is not None:
            executor_patcher.patch()

    # Queue metrics engine: subscribe to raw queue events whether or not
    # the patcher is active — third-party publishers can still emit queue
    # events into the bus. ``start()`` is idempotent and safe even if the
    # engine has no bus.
    queue_metrics_engine = getattr(app.state, "queue_metrics_engine", None)
    if queue_metrics_engine is not None:
        queue_metrics_engine.start()
    executor_metrics_engine = getattr(app.state, "executor_metrics_engine", None)
    if executor_metrics_engine is not None:
        executor_metrics_engine.start()

    # Event-loop lag monitor: deliberately NOT started here.
    #
    # The dashboard server runs on its own daemon-thread event loop
    # (uvicorn). The lag sampler observes whichever loop it is bound
    # to — if we started it here it would sample the *uvicorn* loop,
    # which never blocks, and would silently miss every blocking call
    # the user's workload makes on its own loop. Instead we keep the
    # monitor IDLE and let the CLI bootstrap (or any programmatic
    # caller) bind it to the user's loop once that loop exists via
    # :meth:`EventLoopLagMonitor.bind_to_loop_threadsafe`.
    #
    # Detector + capture + emitter wiring still happens unconditionally
    # below — those are passive subscriptions; the monitor will start
    # publishing measurements once it's bound to a real loop, at which
    # point the downstream pipeline activates automatically.
    #
    # The detector / capture / emitter still need ``start()`` so their
    # own internal state (subscriber registries, dedup tables) is
    # ready to receive events the moment the monitor binds.
    await blocking_detector.start()
    blocking_detector.bind_to_monitor(lag_monitor)

    # Blocking stack-capture engine: subscribes to the blocking
    # detector's outcomes and emits serialized frame captures through
    # the bus. Must start AFTER the detector and bind to it explicitly.
    await stack_capture_engine.start()
    stack_capture_engine.bind_to_detector(blocking_detector)

    # Blocking warning emitter: subscribes to both the detector + the
    # capture engine and surfaces per-window warning groups with full
    # lifecycle. Starts last so it sees the complete view from the
    # very first sample.
    await blocking_warning_emitter.start()
    blocking_warning_emitter.bind_to_detector(blocking_detector)
    blocking_warning_emitter.bind_to_capture_engine(stack_capture_engine)

    logger.info(
        "Dashboard lifespan starting (heartbeat=%.2fs, instrumentation=%s, bridge=on)",
        config.heartbeat_interval,
        "on" if config.enable_instrumentation else "off",
    )

    heartbeat_task = asyncio.create_task(
        _heartbeat_loop(runtime_state, manager, metrics, config.heartbeat_interval),
        name="asyncviz-heartbeat",
    )

    try:
        yield
    finally:
        # Cancel the lifespan-owned background task before delegating
        # service teardown. The coordinator owns service stops; the
        # heartbeat is owned by this scope and dies cleanly here.
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task

        # Tear down state-store subscriptions before running the
        # coordinator's stopping phase. Subscriptions live on the
        # lifespan side because they were registered here; the
        # coordinator stops the producer services (bus, queue, bridge)
        # which would surface "no subscriber" warnings if we didn't
        # unhook in this order.
        with contextlib.suppress(Exception):
            state_store.unsubscribe(replay_subscription)
        with contextlib.suppress(Exception):
            state_store.unsubscribe(warning_subscription)
        with contextlib.suppress(Exception):
            state_store.unsubscribe(metrics_subscription)
        with contextlib.suppress(Exception):
            state_store.unsubscribe(timeline_subscription)
        if state_store_subscription is not None:
            with contextlib.suppress(Exception):
                event_bus.unsubscribe(state_store_subscription)

        # Delegate the rest of the teardown to the coordinator. Inside
        # ``run`` it: (1) notifies websocket clients, (2) drains the
        # queue, (3) captures a final checkpoint + snapshot, (4) stops
        # services in deterministic order, (5) disconnects clients.
        report = await coordinator.run(reason="lifespan")
        logger.info(
            "Dashboard lifespan stopped (phase=%s, duration_ns=%d, errors=%d)",
            report.final_phase.value,
            report.total_duration_ns,
            len(report.errors),
        )


async def _heartbeat_loop(
    runtime_state: RuntimeState,
    manager: ConnectionManager,
    metrics: MetricsState,
    interval: float,
) -> None:
    while True:
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            return
        envelope = heartbeat(
            uptime_seconds=runtime_state.uptime_seconds,
            connected_clients=manager.client_count,
        )
        delivered = await manager.broadcast(envelope)
        if delivered:
            metrics.inc_ws_messages(delivered)
