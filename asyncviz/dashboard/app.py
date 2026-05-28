from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from asyncviz.config import AsyncVizConfig
from asyncviz.dashboard.frontend_serving import (
    CACHE_IMMUTABLE,
    CACHE_NO_CACHE,
    CACHE_SHORT,
    FrontendServingConfig,
    FrontendServingService,
    locate_static_dir,
)
from asyncviz.dashboard.health import HealthService
from asyncviz.dashboard.lifespan import lifespan
from asyncviz.dashboard.middleware import (
    CorrelationIdMiddleware,
    ErrorNormalizationMiddleware,
    RequestLoggingMiddleware,
    RequestTimingMiddleware,
)
from asyncviz.dashboard.routes import api_router, websocket_router
from asyncviz.dashboard.snapshots import SnapshotService
from asyncviz.dashboard.state.backend import BackendAppState
from asyncviz.dashboard.state.backend_metrics import BackendMetrics
from asyncviz.dashboard.state.metrics_state import MetricsState
from asyncviz.dashboard.state.runtime_state import RuntimeState
from asyncviz.dashboard.websocket.bridge import WebSocketBridge
from asyncviz.dashboard.websocket.gateway import WebSocketGateway
from asyncviz.dashboard.websocket.manager import ConnectionManager
from asyncviz.dashboard.websocket.streaming import RuntimeStreamingEngine
from asyncviz.instrumentation.asyncio import AsyncioPatcher
from asyncviz.packaging import package_version
from asyncviz.runtime.clock import RuntimeClock, set_default_runtime_clock
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.metrics import RuntimeMetricsAggregator
from asyncviz.runtime.monitoring import (
    BlockingDetectorConfiguration,
    BlockingStackCaptureEngine,
    BlockingThresholdDetector,
    EventLoopLagMonitor,
    LagConfiguration,
    StackCaptureConfiguration,
)
from asyncviz.runtime.queue import InternalEventQueue
from asyncviz.runtime.replay import EventReplayBuffer
from asyncviz.runtime.shutdown import RuntimeShutdownCoordinator
from asyncviz.runtime.state import RuntimeStateStore
from asyncviz.runtime.tasks import TaskRegistry
from asyncviz.runtime.timeline import TimelineSegmentEngine
from asyncviz.runtime.warnings import RuntimeWarningManager
from asyncviz.runtime.warnings.blocking import (
    BlockingWarningConfiguration,
    BlockingWarningEmitter,
)
from asyncviz.utils.logging import get_logger

logger = get_logger("dashboard.app")

#: Legacy attribute retained for backward compatibility. The canonical
#: source of truth is :class:`FrontendServingConfig.static_dir`; tests
#: that monkey-patch this attribute still work because the service is
#: constructed off of it inside :func:`create_app`.
STATIC_DIR: Path = locate_static_dir()

#: Re-exported here for backward compatibility — moved to
#: :mod:`asyncviz.dashboard.frontend_serving.cache`.
CACHE_NO_STORE = CACHE_NO_CACHE
__all__ = ("CACHE_IMMUTABLE", "CACHE_NO_STORE", "CACHE_SHORT", "STATIC_DIR", "create_app")


def create_app(config: AsyncVizConfig | None = None) -> FastAPI:
    """Build a fresh embedded AsyncViz FastAPI app.

    Safe to call repeatedly — each call returns an isolated app with its own
    state, routers, and websocket manager.
    """
    config = config or AsyncVizConfig()
    app = FastAPI(
        title="AsyncViz",
        version=package_version(),
        debug=config.debug,
        lifespan=lifespan,
    )

    # Construct the runtime clock first so every downstream service uses it
    # as the canonical timing source. We also install it as the process-wide
    # default so ad-hoc event constructors (Pydantic default_factory hooks)
    # share its ``runtime_id`` and ordering domain.
    runtime_clock = RuntimeClock()
    set_default_runtime_clock(runtime_clock)

    app.state.config = config
    app.state.runtime_clock = runtime_clock
    app.state.runtime_state = RuntimeState()
    app.state.runtime_state.bind_clock(runtime_clock)
    app.state.metrics_state = MetricsState()
    app.state.websocket_manager = ConnectionManager()
    # Queue first — the bus delegates to it, so it must exist before the bus.
    app.state.event_queue = InternalEventQueue(clock=runtime_clock)
    app.state.event_bus = EventBus()
    app.state.event_bus.attach_event_queue(app.state.event_queue)
    app.state.task_registry = TaskRegistry()
    # State store wraps the registry and serves as the canonical derived-state
    # surface for the dashboard, websocket bridge, and future replay tools.
    app.state.state_store = RuntimeStateStore(
        app.state.task_registry,
        clock=runtime_clock,
    )
    # Timeline engine subscribes to state-store StateChange notifications.
    # The lifespan installs the subscription so it survives test teardown.
    app.state.timeline_engine = TimelineSegmentEngine(clock=runtime_clock)
    # Metrics aggregator subscribes to the same StateChange stream. It
    # consults the timeline engine at snapshot time for segment-level
    # summaries, so it must be constructed after the engine.
    app.state.metrics_aggregator = RuntimeMetricsAggregator(
        app.state.task_registry,
        clock=runtime_clock,
        timeline_engine=app.state.timeline_engine,
    )
    # Warning manager subscribes to state changes and reads metrics / lineage
    # at evaluation time. Default detector set is registered by the manager.
    app.state.warning_manager = RuntimeWarningManager(
        app.state.task_registry,
        aggregator=app.state.metrics_aggregator,
        clock=runtime_clock,
    )
    # Replay buffer subscribes to state changes too — it logs every applied
    # event with its sequence so reconnecting clients can resume cleanly.
    app.state.replay_buffer = EventReplayBuffer(clock=runtime_clock)
    # Event-loop lag monitor: low-overhead asyncio-cadence sampler that feeds
    # the warning / metrics surfaces with runtime-latency observations. The
    # emitter is wired to the event bus's synchronous ``publish`` so threshold
    # breaches flow through the same path as task events.
    app.state.lag_monitor = EventLoopLagMonitor(
        runtime_clock=runtime_clock,
        configuration=LagConfiguration.default(),
        event_emitter=app.state.event_bus.publish,
    )
    # Blocking-threshold detector: classifies lag measurements, tracks
    # escalation pressure + freeze-window lifecycle, and emits replay-safe
    # blocking events through the bus. Subscribes to the lag monitor at
    # lifespan startup so it observes every measurement.
    app.state.blocking_detector = BlockingThresholdDetector(
        runtime_clock=runtime_clock,
        configuration=BlockingDetectorConfiguration.default(),
        event_emitter=app.state.event_bus.publish,
    )
    # Blocking stack-frame capture engine: walks the Python frame stack
    # at the moment a blocking violation is detected and emits a
    # serialized, bounded, replay-safe capture event. Subscribes to the
    # blocking detector at lifespan startup; tied to the task registry
    # so captures carry asyncio task/coroutine context.
    app.state.stack_capture_engine = BlockingStackCaptureEngine(
        runtime_clock=runtime_clock,
        configuration=StackCaptureConfiguration.default(),
        event_emitter=app.state.event_bus.publish,
        task_registry=app.state.task_registry,
    )
    # Blocking warning emitter: aggregates detector outcomes + stack
    # captures into per-window warning groups with full lifecycle
    # (opened → escalating → active → recovered → expired) and emits
    # canonical group transition events. Subscribes to both the
    # detector and the capture engine at lifespan startup so it sees
    # every outcome + every correlated trace.
    app.state.blocking_warning_emitter = BlockingWarningEmitter(
        runtime_clock=runtime_clock,
        configuration=BlockingWarningConfiguration.default(),
        event_emitter=app.state.event_bus.publish,
    )
    app.state.patcher = AsyncioPatcher(app.state.event_bus, runtime_id=runtime_clock.runtime_id)
    # Queue instrumentor — patched lifecycle managed by AsyncioPatcher's
    # bootstrap when ``enable_instrumentation`` is true.
    from asyncviz.instrumentation.queue import QueueInstrumentationEngine

    app.state.queue_patcher = QueueInstrumentationEngine(bus=app.state.event_bus)

    # Queue metrics engine — subscribes to raw asyncio.queue.* events on the
    # bus and emits aggregated ``metrics.updated`` / ``pressure.changed`` /
    # ``contention.detected`` / ``saturation.detected`` events. Started in
    # the lifespan (after the bus is up) and stopped via the coordinator.
    from asyncviz.instrumentation.queue.metrics import QueueMetricsEngine

    app.state.queue_metrics_engine = QueueMetricsEngine(bus=app.state.event_bus)

    # Semaphore patcher — emits ``asyncio.semaphore.*`` events on every
    # acquire / release / cancel. Patched alongside the asyncio + queue
    # patchers in the lifespan; the shutdown coordinator unpatches it.
    from asyncviz.instrumentation.semaphore import SemaphoreInstrumentationEngine

    app.state.semaphore_patcher = SemaphoreInstrumentationEngine(
        bus=app.state.event_bus,
    )

    # Gather patcher — emits ``asyncio.gather.*`` events on every
    # await-group fanout. Child task ids are resolved through the
    # asyncio patcher's TaskContext so they align with the timeline's
    # runtime_task_id namespace; the resolver falls back to ``get_name``
    # and finally an ``id()``-derived synthetic id.
    from asyncviz.instrumentation.gather import GatherInstrumentationEngine

    _task_context = getattr(app.state.patcher, "context", None)

    def _resolve_gather_child_id(child: object) -> str | None:
        if _task_context is not None:
            try:
                resolved = _task_context.get(child)  # type: ignore[arg-type]
            except Exception:
                resolved = None
            if isinstance(resolved, str) and resolved:
                return resolved
        name = getattr(child, "get_name", None)
        if callable(name):
            try:
                value = name()
            except Exception:
                return None
            if isinstance(value, str) and value:
                return value
        return None

    app.state.gather_patcher = GatherInstrumentationEngine(
        bus=app.state.event_bus,
        task_id_resolver=_resolve_gather_child_id,
    )

    # Executor patcher — emits ``asyncio.executor.*`` events for every
    # ``loop.run_in_executor`` call. Captures submitting task,
    # callable name, worker thread name, and lifecycle (submitted /
    # started / completed / failed / cancelled).
    from asyncviz.instrumentation.executor import ExecutorInstrumentationEngine

    app.state.executor_patcher = ExecutorInstrumentationEngine(
        bus=app.state.event_bus,
    )

    # Executor metrics engine — subscribes to raw ``asyncio.executor.*``
    # events and emits aggregated ``metrics.updated`` / ``saturation.changed`` /
    # ``contention.detected`` / ``latency.spike.detected`` events. Lifecycle
    # tied to the lifespan (started after the bus, stopped via the coordinator).
    from asyncviz.instrumentation.executor.metrics import ExecutorMetricsEngine

    app.state.executor_metrics_engine = ExecutorMetricsEngine(
        bus=app.state.event_bus,
    )

    app.state.websocket_bridge = WebSocketBridge(
        app.state.event_bus,
        app.state.websocket_manager,
        app.state.metrics_state,
        clock=runtime_clock,
        event_queue=app.state.event_queue,
        state_store=app.state.state_store,
    )

    # Backend-side observability counters — populated by middleware.
    app.state.backend_metrics = BackendMetrics()

    # Snapshot service: composes the canonical RuntimeSnapshot from the
    # state-store, timeline engine, metrics aggregator, warning manager,
    # replay buffer, and event queue under a single consistency cursor.
    # Constructed before the streaming engine so handlers, the gateway,
    # and the streaming layer can all reach the same hydration surface.
    app.state.snapshot_service = SnapshotService(
        clock=runtime_clock,
        state_store=app.state.state_store,
        timeline_engine=app.state.timeline_engine,
        metrics_aggregator=app.state.metrics_aggregator,
        warning_manager=app.state.warning_manager,
        replay_buffer=app.state.replay_buffer,
        event_queue=app.state.event_queue,
    )

    # Streaming engine: subscribes to metrics_aggregator + warning_manager +
    # timeline_engine and broadcasts typed ``metrics_delta`` / ``warning_delta``
    # / ``timeline_delta`` envelopes via the connection manager. Constructed
    # here so handlers can reach it through ``app.state.streaming_engine`` /
    # ``app.state.backend.streaming_engine``; the lifespan owns start/stop.
    app.state.streaming_engine = RuntimeStreamingEngine(
        manager=app.state.websocket_manager,
        clock=runtime_clock,
        metrics_aggregator=app.state.metrics_aggregator,
        warning_manager=app.state.warning_manager,
        timeline_engine=app.state.timeline_engine,
    )

    # Per-session websocket orchestrator. Composes the connection manager,
    # bridge, and replay buffer; owns its own session registry + metrics.
    app.state.websocket_gateway = WebSocketGateway(
        manager=app.state.websocket_manager,
        bridge=app.state.websocket_bridge,
        clock=runtime_clock,
        registry=app.state.task_registry,
        replay_buffer=app.state.replay_buffer,
        backend_metrics=app.state.backend_metrics,
    )

    # Typed backend state container — the canonical place handlers /
    # middleware read service references from. Coexists with the legacy
    # ``app.state.X`` references during the migration window.
    app.state.backend = BackendAppState(
        config=config,
        runtime_clock=runtime_clock,
        runtime_state=app.state.runtime_state,
        metrics_state=app.state.metrics_state,
        metrics=app.state.backend_metrics,
        websocket_manager=app.state.websocket_manager,
        websocket_bridge=app.state.websocket_bridge,
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
        patcher=app.state.patcher,
        lag_monitor=app.state.lag_monitor,
        blocking_detector=app.state.blocking_detector,
        stack_capture_engine=app.state.stack_capture_engine,
        blocking_warning_emitter=app.state.blocking_warning_emitter,
    )

    # Health service is constructed last because it inspects every other
    # subsystem at evaluation time — every probe reads through the typed
    # ``BackendAppState`` rather than capturing references directly, so
    # it stays decoupled from construction order in user-extended setups.
    app.state.health_service = HealthService(state=app.state.backend)
    app.state.backend.health_service = app.state.health_service

    # Shutdown coordinator: the single owner of the teardown sequence.
    # Capturing service references at construction time keeps lifespan
    # logic side-effect-free.
    app.state.shutdown_coordinator = RuntimeShutdownCoordinator(
        runtime_state=app.state.runtime_state,
        websocket_manager=app.state.websocket_manager,
        websocket_bridge=app.state.websocket_bridge,
        streaming_engine=app.state.streaming_engine,
        event_bus=app.state.event_bus,
        event_queue=app.state.event_queue,
        task_registry=app.state.task_registry,
        state_store=app.state.state_store,
        replay_buffer=app.state.replay_buffer,
        snapshot_service=app.state.snapshot_service,
        patcher=app.state.patcher,
        lag_monitor=app.state.lag_monitor,
        blocking_detector=app.state.blocking_detector,
        stack_capture_engine=app.state.stack_capture_engine,
        blocking_warning_emitter=app.state.blocking_warning_emitter,
    )
    # Attach the queue patcher so the coordinator's _stop_services
    # path unpatches it alongside the asyncio patcher. The attribute is
    # optional — the coordinator probes for it defensively.
    app.state.shutdown_coordinator._queue_patcher = app.state.queue_patcher  # type: ignore[attr-defined]
    # Same idea — the coordinator probes for an optional engine attribute
    # and stops it after the bus is drained but before services shut down.
    app.state.shutdown_coordinator._queue_metrics_engine = app.state.queue_metrics_engine  # type: ignore[attr-defined]
    # Semaphore patcher attaches in the same defensive style.
    app.state.shutdown_coordinator._semaphore_patcher = app.state.semaphore_patcher  # type: ignore[attr-defined]
    # Gather patcher attaches similarly.
    app.state.shutdown_coordinator._gather_patcher = app.state.gather_patcher  # type: ignore[attr-defined]
    # Executor patcher attaches similarly.
    app.state.shutdown_coordinator._executor_patcher = app.state.executor_patcher  # type: ignore[attr-defined]
    app.state.shutdown_coordinator._executor_metrics_engine = app.state.executor_metrics_engine  # type: ignore[attr-defined]
    app.state.backend.shutdown_coordinator = app.state.shutdown_coordinator

    # Frontend serving: resolves the embedded bundle, discovers the
    # manifest, and (when applicable) mounts the SPA + /assets/ routes.
    # ``STATIC_DIR`` is the legacy attribute tests monkey-patch — read
    # it here at construction time so test overrides take effect.
    app.state.frontend_serving = FrontendServingService(
        FrontendServingConfig(static_dir=STATIC_DIR, mode=config.frontend_mode),
    )
    app.state.backend.frontend_serving = app.state.frontend_serving

    _register_middleware(app, config)
    app.include_router(api_router, prefix="/api")
    app.include_router(websocket_router)
    app.state.frontend_serving.mount(app)
    return app


def _register_middleware(app: FastAPI, config: AsyncVizConfig) -> None:
    # Order is important — see ``dashboard/middleware/__init__.py`` for the
    # rationale. We add CORS first (so it lives at the *outermost* layer
    # the client sees) then the rest in reverse-execution order.
    _register_cors_middleware(app, config)
    # Outermost typed layer: turn raw exceptions into our canonical JSON envelope.
    app.add_middleware(ErrorNormalizationMiddleware)
    # Then structured logging (depends on timing's ``response_time_ms``).
    app.add_middleware(RequestLoggingMiddleware)
    # Then timing (depends on correlation id for log correlation downstream).
    app.add_middleware(RequestTimingMiddleware)
    # Innermost: correlation id — runs first on the request path so every
    # downstream layer can read it.
    app.add_middleware(CorrelationIdMiddleware)


def _register_cors_middleware(app: FastAPI, config: AsyncVizConfig) -> None:
    """Attach :class:`CORSMiddleware` with config-driven origin handling.

    Behavior matrix:

    * ``cors_allowed_origins`` empty → no middleware. Same-origin
      deployments don't need CORS; skipping the middleware avoids the
      per-request overhead.
    * ``cors_allowed_origins`` is ``("*",)`` → wildcard allow with
      ``allow_credentials=False``. The browser refuses credentialed
      requests against ``*``; setting the flag would produce a runtime
      Starlette warning and a broken behavior contract.
    * Otherwise → explicit allow-list echoed verbatim with
      ``allow_credentials=True``. This is the safe default and supports
      future cookie / auth-header use cases.

    The dev origins ``http://localhost:5173`` + ``http://127.0.0.1:5173``
    ship as defaults so the Vite standalone workflow Just Works without
    needing any operator config. They are harmless in production —
    only a request originating from one of those origins gets the
    ``Access-Control-Allow-Origin`` echo.
    """
    origins = tuple(config.cors_allowed_origins)
    if not origins:
        logger.debug("CORS middleware not registered (cors_allowed_origins is empty)")
        return
    wildcard = origins == ("*",)
    allow_credentials = not wildcard
    if wildcard:
        logger.info(
            "CORS configured with wildcard origins — credentials disabled per browser spec",
        )
    else:
        logger.debug("CORS origins=%s allow_credentials=True", origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app = create_app()