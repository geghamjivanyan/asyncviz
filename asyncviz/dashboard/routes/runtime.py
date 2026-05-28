from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from asyncviz.dashboard.dependencies import (
    get_backend_metrics,
    get_blocking_detector,
    get_blocking_warning_emitter,
    get_event_queue,
    get_frontend_serving,
    get_lag_monitor,
    get_metrics_aggregator,
    get_metrics_state,
    get_replay_buffer,
    get_runtime_clock,
    get_runtime_state,
    get_shutdown_coordinator,
    get_snapshot_service,
    get_stack_capture_engine,
    get_state_store,
    get_streaming_engine,
    get_task_registry,
    get_timeline_engine,
    get_warning_manager,
    get_websocket_gateway,
    get_websocket_manager,
)
from asyncviz.dashboard.frontend_serving import (
    FrontendInfoResponse,
    FrontendManifestEntry,
    FrontendServingMetricsResponse,
    FrontendServingService,
)
from asyncviz.dashboard.snapshots import (
    HydrationOptions,
    RuntimeSnapshot,
    RuntimeSnapshotMetricsResponse,
    SnapshotService,
)
from asyncviz.dashboard.state.backend_metrics import BackendMetrics
from asyncviz.dashboard.state.metrics_state import MetricsState
from asyncviz.dashboard.state.runtime_state import RuntimeState
from asyncviz.dashboard.websocket.gateway import WebSocketGateway
from asyncviz.dashboard.websocket.manager import ConnectionManager
from asyncviz.dashboard.websocket.protocol import PROTOCOL_VERSION
from asyncviz.dashboard.websocket.streaming import RuntimeStreamingEngine
from asyncviz.runtime.clock import ClockSnapshot, RuntimeClock
from asyncviz.runtime.lineage import LineageSnapshot, snapshot_lineage
from asyncviz.runtime.metrics import (
    RuntimeMetricsAggregateSnapshot,
    RuntimeMetricsAggregator,
)
from asyncviz.runtime.monitoring import (
    BlockingStackCaptureEngine,
    BlockingThresholdDetector,
    EventLoopLagMonitor,
)
from asyncviz.runtime.queue import InternalEventQueue, QueueSnapshotResponse
from asyncviz.runtime.replay import (
    EventReplayBuffer,
    ReplayBatchModel,
    ReplayCheckpointModel,
    ReplaySnapshot,
)
from asyncviz.runtime.shutdown import (
    PhaseTimingPayload,
    RuntimeShutdownCoordinator,
    ShutdownMetricsResponse,
    ShutdownReportPayload,
    ShutdownStatusResponse,
)
from asyncviz.runtime.state import RuntimeStateSnapshot, RuntimeStateStore
from asyncviz.runtime.tasks import TaskRegistry, TaskSnapshot
from asyncviz.runtime.timeline import TimelineSegmentEngine, TimelineSnapshot
from asyncviz.runtime.warnings import RuntimeWarningManager, WarningSnapshot
from asyncviz.runtime.warnings.blocking import BlockingWarningEmitter

router = APIRouter(prefix="/runtime", tags=["runtime"])


class RuntimeStatusResponse(BaseModel):
    status: str
    uptime_seconds: float
    connected_clients: int
    protocol_version: str


class RuntimeMetricsResponse(BaseModel):
    events_emitted: int
    websocket_messages_sent: int
    tasks_total: int
    tasks_active: int
    tasks_completed: int
    tasks_cancelled: int
    tasks_failed: int
    tasks_terminal: int
    average_duration_seconds: float | None
    average_completed_duration_seconds: float | None
    average_cancelled_duration_seconds: float | None
    average_failed_duration_seconds: float | None
    cancellations_by_origin: dict[str, int]
    rejected_transitions: int
    runtime_uptime_seconds: float
    sequence_issued: int
    queue_depth: int
    queue_capacity: int
    queue_published: int
    queue_dispatched: int
    queue_dropped_overflow: int
    queue_retained: int
    queue_replay_hits: int
    queue_replay_misses: int
    lineage_tracked_tasks: int
    lineage_root_tasks: int
    lineage_max_depth: int
    lineage_orphan_links: int
    lineage_cyclic_rejections: int
    state_events_applied: int
    state_events_stale: int
    state_events_duplicate: int
    state_events_unknown_type: int
    state_events_rejected: int
    state_last_sequence: int
    state_snapshots_emitted: int
    state_subscription_dispatches: int
    timeline_transitions_applied: int
    timeline_transitions_rejected: int
    timeline_segments_opened: int
    timeline_segments_closed: int
    timeline_active_segments: int
    timeline_finalized_spans: int
    timeline_invalid_transitions: int
    timeline_rebuilds_completed: int


class TasksResponse(BaseModel):
    tasks: list[TaskSnapshot]
    total: int
    active: int


class GatewaySessionsByState(BaseModel):
    """Breakdown of active sessions by lifecycle state."""

    pending: int = 0
    hydrating: int = 0
    live: int = 0
    draining: int = 0
    closed: int = 0


class GatewaySessionMetricsModel(BaseModel):
    """Aggregate per-session counters across every active session."""

    messages_sent: int
    messages_dropped: int
    heartbeats_sent: int
    heartbeats_missed: int
    send_failures: int
    bytes_sent: int
    backpressure_events: int


class GatewayMetricsResponse(BaseModel):
    """Snapshot of :class:`WebSocketGateway` observability counters."""

    sessions_opened: int
    sessions_closed: int
    sessions_active: int
    handshake_replay_hits: int
    handshake_replay_misses: int
    handshake_snapshot_hydrations: int
    messages_sent: int
    messages_dropped: int
    heartbeats_sent: int
    sessions_stale_evicted: int
    protocol_errors: int
    sessions_by_state: GatewaySessionsByState
    aggregate_session_metrics: GatewaySessionMetricsModel


class StreamingMetricsResponse(BaseModel):
    """Snapshot of :class:`RuntimeStreamingEngine` self-observability counters.

    ``metrics_deltas_sent`` / ``warning_deltas_sent`` / ``timeline_deltas_sent``
    track how many envelopes the engine has fanned out on each stream;
    ``subscription_dispatches`` / ``subscription_failures`` track the upstream
    callback path (subscriptions firing into the engine); ``broadcast_failures``
    counts fanout-side failures from :class:`ConnectionManager.broadcast`.
    """

    running: bool
    metrics_deltas_sent: int
    warning_deltas_sent: int
    timeline_deltas_sent: int
    runtime_deltas_sent: int
    protocol_errors_sent: int
    subscription_dispatches: int
    subscription_failures: int
    broadcast_failures: int


class BackendMetricsResponse(BaseModel):
    """Backend's own request / websocket-lifecycle counters."""

    requests_total: int
    requests_in_flight: int
    requests_by_status: dict[str, int]
    requests_by_method: dict[str, int]
    average_duration_ms: float
    max_duration_ms: float
    api_errors_total: int
    api_errors_by_code: dict[str, int]
    ws_connections_total: int
    ws_disconnections_total: int
    ws_active_connections: int


@router.get("/status", response_model=RuntimeStatusResponse)
async def runtime_status(
    runtime: Annotated[RuntimeState, Depends(get_runtime_state)],
    manager: Annotated[ConnectionManager, Depends(get_websocket_manager)],
) -> RuntimeStatusResponse:
    return RuntimeStatusResponse(
        status=runtime.status,
        uptime_seconds=runtime.uptime_seconds,
        connected_clients=manager.client_count,
        protocol_version=PROTOCOL_VERSION,
    )


@router.get("/metrics", response_model=RuntimeMetricsResponse)
async def runtime_metrics(
    metrics: Annotated[MetricsState, Depends(get_metrics_state)],
    registry: Annotated[TaskRegistry, Depends(get_task_registry)],
    clock: Annotated[RuntimeClock, Depends(get_runtime_clock)],
    queue: Annotated[InternalEventQueue, Depends(get_event_queue)],
    store: Annotated[RuntimeStateStore, Depends(get_state_store)],
    timeline: Annotated[TimelineSegmentEngine, Depends(get_timeline_engine)],
) -> RuntimeMetricsResponse:
    ws_snap = metrics.snapshot()
    task_snap = registry.metrics_snapshot()
    clock_metrics = clock.metrics_snapshot()
    queue_metrics = queue.metrics_snapshot()
    lineage_metrics = registry.lineage_metrics_snapshot()
    state_metrics = store.metrics_snapshot()
    timeline_metrics = timeline.metrics_snapshot()
    return RuntimeMetricsResponse(
        events_emitted=ws_snap.events_emitted,
        websocket_messages_sent=ws_snap.websocket_messages_sent,
        tasks_total=task_snap.total_tasks,
        tasks_active=task_snap.active_tasks,
        tasks_completed=task_snap.completed_tasks,
        tasks_cancelled=task_snap.cancelled_tasks,
        tasks_failed=task_snap.failed_tasks,
        tasks_terminal=task_snap.terminal_tasks,
        average_duration_seconds=task_snap.average_duration_seconds,
        average_completed_duration_seconds=task_snap.average_completed_duration_seconds,
        average_cancelled_duration_seconds=task_snap.average_cancelled_duration_seconds,
        average_failed_duration_seconds=task_snap.average_failed_duration_seconds,
        cancellations_by_origin=task_snap.cancellations_by_origin,
        rejected_transitions=task_snap.rejected_transitions,
        runtime_uptime_seconds=clock_metrics.uptime_seconds,
        sequence_issued=clock_metrics.sequence_issued,
        queue_depth=queue_metrics.depth,
        queue_capacity=queue_metrics.capacity,
        queue_published=queue_metrics.published,
        queue_dispatched=queue_metrics.dispatched,
        queue_dropped_overflow=queue_metrics.dropped_overflow,
        queue_retained=queue_metrics.retained,
        queue_replay_hits=queue_metrics.replay_hits,
        queue_replay_misses=queue_metrics.replay_misses,
        lineage_tracked_tasks=lineage_metrics.tracked_tasks,
        lineage_root_tasks=lineage_metrics.root_tasks,
        lineage_max_depth=lineage_metrics.max_depth,
        lineage_orphan_links=lineage_metrics.orphan_links,
        lineage_cyclic_rejections=lineage_metrics.cyclic_rejections,
        state_events_applied=state_metrics.events_applied,
        state_events_stale=state_metrics.events_stale,
        state_events_duplicate=state_metrics.events_duplicate,
        state_events_unknown_type=state_metrics.events_unknown_type,
        state_events_rejected=state_metrics.events_rejected,
        state_last_sequence=state_metrics.last_event_sequence,
        state_snapshots_emitted=state_metrics.snapshots_emitted,
        state_subscription_dispatches=state_metrics.subscription_dispatches,
        timeline_transitions_applied=timeline_metrics.transitions_applied,
        timeline_transitions_rejected=timeline_metrics.transitions_rejected,
        timeline_segments_opened=timeline_metrics.segments_opened,
        timeline_segments_closed=timeline_metrics.segments_closed,
        timeline_active_segments=timeline_metrics.active_segments,
        timeline_finalized_spans=timeline_metrics.finalized_spans,
        timeline_invalid_transitions=timeline_metrics.invalid_transitions,
        timeline_rebuilds_completed=timeline_metrics.rebuilds_completed,
    )


@router.get("/tasks", response_model=TasksResponse)
async def list_tasks(
    registry: Annotated[TaskRegistry, Depends(get_task_registry)],
    active_only: bool = False,
) -> TasksResponse:
    """Return a deterministic snapshot of observed asyncio tasks.

    ``active_only=true`` filters out terminal states (completed/cancelled/failed).
    """
    snap = registry.snapshot_active_tasks() if active_only else registry.snapshot_all_tasks()
    metrics = registry.metrics_snapshot()
    return TasksResponse(
        tasks=list(snap),
        total=metrics.total_tasks,
        active=metrics.active_tasks,
    )


@router.get("/tasks/{task_id}", response_model=TaskSnapshot)
async def get_task(
    task_id: str,
    registry: Annotated[TaskRegistry, Depends(get_task_registry)],
) -> TaskSnapshot:
    snap = registry.snapshot_task(task_id)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"task {task_id!r} not found")
    return snap


@router.get("/clock", response_model=ClockSnapshot)
async def runtime_clock(
    clock: Annotated[RuntimeClock, Depends(get_runtime_clock)],
) -> ClockSnapshot:
    """Return the canonical clock snapshot.

    Authoritative source of wall-clock, monotonic time, uptime, and the
    current sequence position. Use this from clients to validate that
    timestamps observed locally match the runtime's own time domain.
    """
    return clock.snapshot()


@router.get("/lineage/{task_id}", response_model=LineageSnapshot)
async def runtime_lineage(
    task_id: str,
    registry: Annotated[TaskRegistry, Depends(get_task_registry)],
) -> LineageSnapshot:
    """Return the lineage view for a single task.

    Includes ``parent_task_id``, ``root_task_id``, ``ancestor_chain`` (closest
    first), ``child_count``, and the materialized BFS list of descendants.
    Useful for tree-rendering frontends and replay debuggers.
    """
    snap = snapshot_lineage(registry.lineage, task_id)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"task {task_id!r} not found")
    return snap


@router.get("/state", response_model=RuntimeStateSnapshot)
async def runtime_state_snapshot(
    store: Annotated[RuntimeStateStore, Depends(get_state_store)],
    include_projections: bool = True,
) -> RuntimeStateSnapshot:
    """Return the canonical :class:`RuntimeStateSnapshot`.

    This is the authoritative derived view of the runtime: every task, every
    metric, every lineage rollup, plus the configured projections. Use this
    as the reconnect baseline; the websocket bridge embeds the same shape
    on every ``runtime_snapshot`` frame.

    Pass ``include_projections=false`` for a small payload — useful when
    polling the state at high frequency.
    """
    return store.snapshot(include_projections=include_projections)


@router.get("/gateway", response_model=GatewayMetricsResponse)
async def runtime_gateway_metrics(
    gateway: Annotated[WebSocketGateway, Depends(get_websocket_gateway)],
) -> GatewayMetricsResponse:
    """Return the WebSocket gateway's observability counters.

    Includes session lifecycle counts (opened / closed / active),
    handshake outcomes (replay hits / misses / snapshot hydrations),
    per-session aggregates (messages sent / dropped / bytes), heartbeat +
    stale-eviction counters, and protocol-error tally. Distinct from
    ``/api/runtime/backend`` which tracks HTTP-side counters.
    """
    snap = gateway.metrics_snapshot()
    sessions = gateway.sessions_snapshot()
    by_state = sessions.by_state
    return GatewayMetricsResponse(
        sessions_opened=snap.sessions_opened,
        sessions_closed=snap.sessions_closed,
        sessions_active=snap.sessions_active,
        handshake_replay_hits=snap.handshake_replay_hits,
        handshake_replay_misses=snap.handshake_replay_misses,
        handshake_snapshot_hydrations=snap.handshake_snapshot_hydrations,
        messages_sent=snap.messages_sent,
        messages_dropped=snap.messages_dropped,
        heartbeats_sent=snap.heartbeats_sent,
        sessions_stale_evicted=snap.sessions_stale_evicted,
        protocol_errors=snap.protocol_errors,
        sessions_by_state=GatewaySessionsByState(
            pending=by_state.get("pending", 0),
            hydrating=by_state.get("hydrating", 0),
            live=by_state.get("live", 0),
            draining=by_state.get("draining", 0),
            closed=by_state.get("closed", 0),
        ),
        aggregate_session_metrics=GatewaySessionMetricsModel(
            messages_sent=sessions.aggregate.messages_sent,
            messages_dropped=sessions.aggregate.messages_dropped,
            heartbeats_sent=sessions.aggregate.heartbeats_sent,
            heartbeats_missed=sessions.aggregate.heartbeats_missed,
            send_failures=sessions.aggregate.send_failures,
            bytes_sent=sessions.aggregate.bytes_sent,
            backpressure_events=sessions.aggregate.backpressure_events,
        ),
    )


@router.get("/streaming", response_model=StreamingMetricsResponse)
async def runtime_streaming_metrics(
    engine: Annotated[RuntimeStreamingEngine, Depends(get_streaming_engine)],
) -> StreamingMetricsResponse:
    """Return the realtime streaming engine's observability counters.

    Reports per-stream send totals (``metrics``/``warning``/``timeline``/
    ``runtime`` deltas), the subscription dispatch tally, and broadcast-side
    failures. ``running`` reflects whether the engine has bound its
    upstream subscriptions (set by the dashboard lifespan).
    """
    snap = engine.metrics_snapshot()
    return StreamingMetricsResponse(
        running=engine.is_running,
        metrics_deltas_sent=snap.metrics_deltas_sent,
        warning_deltas_sent=snap.warning_deltas_sent,
        timeline_deltas_sent=snap.timeline_deltas_sent,
        runtime_deltas_sent=snap.runtime_deltas_sent,
        protocol_errors_sent=snap.protocol_errors_sent,
        subscription_dispatches=snap.subscription_dispatches,
        subscription_failures=snap.subscription_failures,
        broadcast_failures=snap.broadcast_failures,
    )


@router.get("/backend", response_model=BackendMetricsResponse)
async def runtime_backend_metrics(
    metrics: Annotated[BackendMetrics, Depends(get_backend_metrics)],
) -> BackendMetricsResponse:
    """Return the FastAPI backend's own observability counters.

    Tracks HTTP request lifecycle (count / in-flight / by-status /
    by-method / average + max latency) plus API error rates and
    websocket connect/disconnect counts. Distinct from
    ``/api/runtime/metrics`` which exposes asyncio-task analytics.
    """
    snap = metrics.snapshot()
    return BackendMetricsResponse(
        requests_total=snap.requests_total,
        requests_in_flight=snap.requests_in_flight,
        requests_by_status=snap.requests_by_status,
        requests_by_method=snap.requests_by_method,
        average_duration_ms=snap.average_duration_ms,
        max_duration_ms=snap.max_duration_ms,
        api_errors_total=snap.api_errors_total,
        api_errors_by_code=snap.api_errors_by_code,
        ws_connections_total=snap.ws_connections_total,
        ws_disconnections_total=snap.ws_disconnections_total,
        ws_active_connections=snap.ws_active_connections,
    )


@router.get("/replay", response_model=ReplaySnapshot)
async def runtime_replay_snapshot(
    buffer: Annotated[EventReplayBuffer, Depends(get_replay_buffer)],
) -> ReplaySnapshot:
    """Return the canonical :class:`ReplaySnapshot`.

    Carries the capacity / current-window bounds + every retained
    checkpoint + the buffer's self-metrics. Use this to answer "what can
    I replay from?" before issuing a sequence-windowed query.
    """
    return buffer.snapshot()


@router.get("/replay/since/{sequence}", response_model=ReplayBatchModel)
async def runtime_replay_since(
    sequence: int,
    buffer: Annotated[EventReplayBuffer, Depends(get_replay_buffer)],
    with_checkpoint: bool = False,
) -> ReplayBatchModel:
    """Return frames with ``frame.sequence > sequence`` plus optional checkpoint.

    ``with_checkpoint=true`` includes the freshest applicable checkpoint
    so the caller can fast-forward state through the snapshot before
    streaming the gap. The result's ``window.hit`` indicates whether the
    requested sequence is still inside retention; on miss the caller
    should fall back to a fresh :class:`RuntimeStateSnapshot`.
    """
    return buffer.replay_since(sequence, with_checkpoint=with_checkpoint)


@router.get("/replay/range", response_model=ReplayBatchModel)
async def runtime_replay_range(
    start: int,
    end: int,
    buffer: Annotated[EventReplayBuffer, Depends(get_replay_buffer)],
) -> ReplayBatchModel:
    """Return frames with ``start <= sequence <= end`` (inclusive)."""
    return buffer.replay_range(start, end)


@router.post("/replay/checkpoint", response_model=ReplayCheckpointModel)
async def runtime_replay_create_checkpoint(
    buffer: Annotated[EventReplayBuffer, Depends(get_replay_buffer)],
    state: Annotated[RuntimeStateStore, Depends(get_state_store)],
    timeline: Annotated[TimelineSegmentEngine, Depends(get_timeline_engine)],
    metrics: Annotated[RuntimeMetricsAggregator, Depends(get_metrics_aggregator)],
    warnings: Annotated[RuntimeWarningManager, Depends(get_warning_manager)],
    label: str | None = None,
) -> ReplayCheckpointModel:
    """Capture a checkpoint pinning state + timeline + metrics + warnings.

    Optional ``label`` (e.g. "before-restart", "rollback-point") is
    carried through the wire shape for human-readable retrieval.
    """
    from asyncviz.runtime.replay import checkpoint_to_model

    checkpoint = buffer.create_checkpoint(
        label=label,
        state_store=state,
        timeline_engine=timeline,
        metrics_aggregator=metrics,
        warning_manager=warnings,
    )
    return checkpoint_to_model(checkpoint)


@router.get("/warnings", response_model=WarningSnapshot)
async def runtime_warnings(
    manager: Annotated[RuntimeWarningManager, Depends(get_warning_manager)],
    evaluate: bool = True,
) -> WarningSnapshot:
    """Return the canonical :class:`WarningSnapshot`.

    Pass ``evaluate=false`` to skip the snapshot-driven detector pass —
    useful for cheap polls when only the currently-active list matters and
    the runtime state hasn't materially changed.
    """
    if evaluate:
        manager.evaluate()
    return manager.snapshot()


@router.get("/aggregate", response_model=RuntimeMetricsAggregateSnapshot)
async def runtime_metrics_aggregate(
    aggregator: Annotated[RuntimeMetricsAggregator, Depends(get_metrics_aggregator)],
) -> RuntimeMetricsAggregateSnapshot:
    """Return the canonical :class:`RuntimeMetricsAggregateSnapshot`.

    Lifecycle counts, duration histograms (p50/p95/p99 by terminal state),
    rolling throughput, per-coroutine roll-ups, lineage rollup, top-N
    longest/shortest tasks, optional timeline summary, and aggregator
    self-observability. This is the dashboard's authoritative analytics
    surface.
    """
    return aggregator.snapshot()


@router.get("/timeline", response_model=TimelineSnapshot)
async def runtime_timeline(
    engine: Annotated[TimelineSegmentEngine, Depends(get_timeline_engine)],
    track_kind: str = "task",
) -> TimelineSnapshot:
    """Return the canonical :class:`TimelineSnapshot`.

    ``track_kind`` selects the grouping strategy:

      * ``"task"`` (default) — one lane per task.
      * ``"root"`` — one lane per root task; descendants stacked.
      * ``"coroutine"`` — one lane per ``coroutine_name``.

    The snapshot contains every finalized segment plus the open (active)
    segment for each task that is still running.
    """
    return engine.snapshot(track_kind=track_kind)


@router.get("/snapshot", response_model=RuntimeSnapshot)
async def runtime_snapshot(
    service: Annotated[SnapshotService, Depends(get_snapshot_service)],
    include_state: bool = True,
    include_timeline: bool = True,
    include_metrics: bool = True,
    include_warnings: bool = True,
    include_replay: bool = True,
    include_queue: bool = True,
    include_projections: bool = True,
    include_transitions: bool = True,
    evaluate_warnings: bool = True,
    timeline_track_kind: str = "task",
    since_sequence: int | None = None,
) -> RuntimeSnapshot:
    """Return the canonical :class:`RuntimeSnapshot`.

    This is the authoritative hydration surface: a single
    logically-consistent view of state + timeline + metrics + warnings +
    replay + queue + clock, pinned to one :attr:`SnapshotConsistency.last_sequence`
    cursor. Frontend bootstrap, reconnect recovery, replay debuggers,
    and offline replay loaders all read from here.

    Selective hydration toggles let callers shrink the payload — e.g.
    ``include_timeline=false`` for a fast metrics-only poll. Defaults
    materialize the full payload so accidental misses always favor
    correctness.

    Pass ``since_sequence`` to have the response record whether the
    replay buffer can still satisfy the gap from that cursor; the
    flag is in :attr:`SnapshotConsistency.replay_window_hit`.
    """
    options = HydrationOptions(
        include_state=include_state,
        include_timeline=include_timeline,
        include_metrics=include_metrics,
        include_warnings=include_warnings,
        include_replay=include_replay,
        include_queue=include_queue,
        include_projections=include_projections,
        include_transitions=include_transitions,
        evaluate_warnings=evaluate_warnings,
        timeline_track_kind=timeline_track_kind,
        since_sequence=since_sequence,
    )
    return service.capture(options)


@router.get(
    "/snapshot/metrics",
    response_model=RuntimeSnapshotMetricsResponse,
)
async def runtime_snapshot_metrics(
    service: Annotated[SnapshotService, Depends(get_snapshot_service)],
) -> RuntimeSnapshotMetricsResponse:
    """Return the snapshot service's self-observability counters.

    Tracks the number of full vs. filtered snapshots generated,
    cumulative + max + last generation timings, and last + max payload
    sizes. Use this to spot snapshots growing past their latency
    budget before they become user-visible.
    """
    snap = service.metrics_snapshot()
    return RuntimeSnapshotMetricsResponse(
        snapshots_generated=snap.snapshots_generated,
        full_snapshots=snap.full_snapshots,
        filtered_snapshots=snap.filtered_snapshots,
        total_generation_ns=snap.total_generation_ns,
        average_generation_ns=snap.average_generation_ns,
        max_generation_ns=snap.max_generation_ns,
        last_generation_ns=snap.last_generation_ns,
        last_payload_bytes=snap.last_payload_bytes,
        max_payload_bytes=snap.max_payload_bytes,
        sources_skipped=snap.sources_skipped,
        consistency_errors=snap.consistency_errors,
    )


@router.get("/frontend", response_model=FrontendInfoResponse)
async def runtime_frontend(
    service: Annotated[FrontendServingService, Depends(get_frontend_serving)],
) -> FrontendInfoResponse:
    """Return the canonical :class:`FrontendInfoResponse`.

    Operationally useful inventory of what the static-frontend layer
    is actually serving: configured mode, on-disk static directory,
    bundle presence, asset count + total size, the build manifest
    (Vite-emitted or filesystem-discovered), and the primary entry
    module + linked CSS.
    """
    manifest = service.manifest
    entry = manifest.entry
    return FrontendInfoResponse(
        mode=service.config.mode,
        static_dir=str(service.config.static_dir),
        bundle_present=service.resolver.has_bundle(),
        assets_dir_present=service.resolver.has_assets_dir(),
        asset_count=service.resolver.asset_count(),
        asset_size_bytes=service.resolver.asset_size_bytes(),
        entry_module=entry.file if entry is not None else None,
        entry_css=list(entry.css) if entry is not None else [],
        manifest_source=manifest.source,
        manifest_entries=[
            FrontendManifestEntry(file=e.file, name=e.name, is_entry=e.is_entry, css=list(e.css))
            for e in manifest.entries
        ],
    )


@router.get(
    "/frontend/metrics",
    response_model=FrontendServingMetricsResponse,
)
async def runtime_frontend_metrics(
    service: Annotated[FrontendServingService, Depends(get_frontend_serving)],
) -> FrontendServingMetricsResponse:
    """Return per-request frontend serving counters.

    Tracks asset hits / misses, SPA fallback hits, reserved-prefix
    blocks, path-traversal blocks, and manifest-load outcomes — the
    canonical observability surface for "is the frontend serving
    behaving like we expect".
    """
    snap = service.metrics_snapshot()
    return FrontendServingMetricsResponse(
        asset_requests=snap.asset_requests,
        asset_hits=snap.asset_hits,
        asset_misses=snap.asset_misses,
        immutable_hits=snap.immutable_hits,
        loose_hits=snap.loose_hits,
        index_served=snap.index_served,
        spa_fallbacks=snap.spa_fallbacks,
        reserved_blocked=snap.reserved_blocked,
        path_traversal_blocked=snap.path_traversal_blocked,
        manifest_loads=snap.manifest_loads,
        manifest_load_failures=snap.manifest_load_failures,
    )


@router.get("/shutdown", response_model=ShutdownStatusResponse)
async def runtime_shutdown_status(
    coordinator: Annotated[RuntimeShutdownCoordinator, Depends(get_shutdown_coordinator)],
) -> ShutdownStatusResponse:
    """Return the live :class:`ShutdownStatusResponse`.

    Polled by dashboards to render the shutdown banner / reconnect
    guidance. ``report`` is only populated once the coordinator has
    reached a terminal phase (``STOPPED`` or ``FAILED``) — frontend
    code reads it to display the post-mortem panel.
    """
    report = coordinator.maybe_report()
    report_payload = None
    if report is not None:
        report_payload = ShutdownReportPayload(
            final_phase=report.final_phase,
            reason=report.reason,
            triggered_at_monotonic_ns=report.triggered_at_monotonic_ns,
            finished_at_monotonic_ns=report.finished_at_monotonic_ns,
            total_duration_ns=report.total_duration_ns,
            phase_timings=[
                PhaseTimingPayload(
                    phase=pt.phase, duration_ns=pt.duration_ns, timed_out=pt.timed_out
                )
                for pt in report.phase_timings
            ],
            timeouts_total=report.timeouts_total,
            forced_disconnects=report.forced_disconnects,
            forced_cancellations=report.forced_cancellations,
            checkpoint_id=report.checkpoint_id,
            snapshot_id=report.snapshot_id,
            final_sequence=report.final_sequence,
            errors=list(report.errors),
        )
    return ShutdownStatusResponse(
        phase=coordinator.phase,
        requested=coordinator.is_requested,
        in_progress=coordinator.is_in_progress,
        completed=coordinator.is_completed,
        report=report_payload,
    )


@router.get("/shutdown/metrics", response_model=ShutdownMetricsResponse)
async def runtime_shutdown_metrics(
    coordinator: Annotated[RuntimeShutdownCoordinator, Depends(get_shutdown_coordinator)],
) -> ShutdownMetricsResponse:
    """Return cumulative shutdown counters across the process lifetime."""
    snap = coordinator.metrics_snapshot()
    return ShutdownMetricsResponse(
        current_phase=snap.current_phase,
        shutdowns_requested=snap.shutdowns_requested,
        shutdowns_completed=snap.shutdowns_completed,
        shutdowns_failed=snap.shutdowns_failed,
        timeouts_total=snap.timeouts_total,
        forced_disconnects=snap.forced_disconnects,
        forced_cancellations=snap.forced_cancellations,
        last_total_duration_ns=snap.last_total_duration_ns,
        max_total_duration_ns=snap.max_total_duration_ns,
    )


@router.get("/queue", response_model=QueueSnapshotResponse)
async def runtime_queue(
    queue: Annotated[InternalEventQueue, Depends(get_event_queue)],
) -> QueueSnapshotResponse:
    """Return the live :class:`InternalEventQueue` snapshot.

    Includes capacity, depth, retention window, and full metrics. Used by
    the dashboard health view and the reconnect protocol: clients can
    consult ``oldest_retained_sequence`` to decide whether a replay request
    is feasible before opening the websocket.
    """
    return queue.snapshot()


class LagMonitorResponse(BaseModel):
    """Lean lag-monitor snapshot for dashboard polling."""

    runtime_id: str
    state: str
    generated_at_monotonic_ns: int
    statistics: dict
    metrics: dict
    last_measurement: dict | None
    configuration: dict


class LagMonitorDiagnosticsResponse(BaseModel):
    """Debug-grade view including trace ring and backpressure state."""

    state: str
    configuration: dict
    statistics: dict
    metrics: dict
    backpressure: dict
    trace: dict


@router.get("/monitoring/lag", response_model=LagMonitorResponse)
async def runtime_lag_monitor(
    monitor: Annotated[EventLoopLagMonitor, Depends(get_lag_monitor)],
) -> LagMonitorResponse:
    """Return the canonical event-loop lag snapshot.

    Lean payload — statistics + metrics + last measurement. For full
    diagnostic detail (trace ring, backpressure state) use
    ``/api/runtime/monitoring/lag/diagnostics``.
    """
    snap = monitor.snapshot()
    return LagMonitorResponse(
        runtime_id=snap.runtime_id,
        state=snap.state.value,
        generated_at_monotonic_ns=snap.generated_at_monotonic_ns,
        statistics=snap.statistics.to_dict(),
        metrics=snap.metrics.to_dict(),
        last_measurement=(
            snap.last_measurement.to_dict() if snap.last_measurement is not None else None
        ),
        configuration=snap.configuration,
    )


@router.get(
    "/monitoring/lag/diagnostics",
    response_model=LagMonitorDiagnosticsResponse,
)
async def runtime_lag_monitor_diagnostics(
    monitor: Annotated[EventLoopLagMonitor, Depends(get_lag_monitor)],
) -> LagMonitorDiagnosticsResponse:
    """Return the debug-grade lag-monitor view.

    Includes the (opt-in) trace ring, backpressure pending/denied
    counters, and the full configuration dict. Intended for the
    diagnostics page; ``trace.records`` is empty unless the monitor
    was configured with ``trace_enabled=True``.
    """
    diag = monitor.diagnostics_snapshot().to_dict()
    return LagMonitorDiagnosticsResponse(**diag)


class BlockingDetectorResponse(BaseModel):
    """Lean blocking-detector snapshot."""

    runtime_id: str
    state: str
    generated_at_monotonic_ns: int
    configuration: dict
    statistics: dict
    metrics: dict
    active_window: dict | None
    recent_windows: list[dict]


class BlockingDetectorDiagnosticsResponse(BaseModel):
    """Debug-grade view including trace ring + backpressure."""

    state: str
    configuration: dict
    statistics: dict
    metrics: dict
    active_window: dict | None
    recent_windows: list[dict]
    backpressure: dict
    trace: dict


@router.get("/monitoring/blocking", response_model=BlockingDetectorResponse)
async def runtime_blocking_detector(
    detector: Annotated[BlockingThresholdDetector, Depends(get_blocking_detector)],
) -> BlockingDetectorResponse:
    """Return the canonical blocking-detector snapshot.

    Includes lifetime window statistics, self-metrics, the currently
    open window (if any), and a bounded history of recent closed
    windows. Pair with ``/api/runtime/monitoring/lag`` for the full
    runtime-latency picture.
    """
    snap = detector.snapshot()
    return BlockingDetectorResponse(
        runtime_id=snap.runtime_id,
        state=snap.state.value,
        generated_at_monotonic_ns=snap.generated_at_monotonic_ns,
        configuration=snap.configuration,
        statistics=snap.statistics.to_dict(),
        metrics=snap.metrics.to_dict(),
        active_window=(snap.active_window.to_dict() if snap.active_window is not None else None),
        recent_windows=[w.to_dict() for w in snap.recent_windows],
    )


@router.get(
    "/monitoring/blocking/diagnostics",
    response_model=BlockingDetectorDiagnosticsResponse,
)
async def runtime_blocking_detector_diagnostics(
    detector: Annotated[BlockingThresholdDetector, Depends(get_blocking_detector)],
) -> BlockingDetectorDiagnosticsResponse:
    """Return the debug-grade blocking-detector view.

    Includes everything the lean snapshot does plus backpressure
    pending/denied counters and the (opt-in) trace ring. The trace ring
    is only populated when the detector was configured with
    ``trace_enabled=True``.
    """
    return BlockingDetectorDiagnosticsResponse(**detector.diagnostics_snapshot().to_dict())


class StackCaptureResponse(BaseModel):
    """Lean stack-capture engine snapshot."""

    runtime_id: str
    state: str
    generated_at_monotonic_ns: int
    configuration: dict
    statistics: dict
    metrics: dict
    recent_captures: list[dict]


class StackCaptureDiagnosticsResponse(BaseModel):
    """Debug-grade stack-capture view (trace + backpressure)."""

    state: str
    configuration: dict
    statistics: dict
    metrics: dict
    recent_captures: list[dict]
    backpressure: dict
    trace: dict


class StackCaptureManualRequest(BaseModel):
    """Operator-triggered capture parameters."""

    trigger: str = "manual"
    severity: str = "NONE"
    window_id: str | None = None
    sample_index: int | None = None


@router.get(
    "/monitoring/blocking/stack_capture",
    response_model=StackCaptureResponse,
)
async def runtime_stack_capture(
    engine: Annotated[BlockingStackCaptureEngine, Depends(get_stack_capture_engine)],
) -> StackCaptureResponse:
    """Return the canonical stack-capture engine snapshot.

    Includes lifetime statistics (captures by severity / trigger / top
    frames), self-metrics, and the recent-capture ring. Pair with
    ``/api/runtime/monitoring/blocking`` to correlate captures with
    their freeze windows.
    """
    snap = engine.snapshot()
    return StackCaptureResponse(
        runtime_id=snap.runtime_id,
        state=snap.state,
        generated_at_monotonic_ns=snap.generated_at_monotonic_ns,
        configuration=snap.configuration,
        statistics=snap.statistics.to_dict(),
        metrics=snap.metrics.to_dict(),
        recent_captures=[c.to_dict() for c in snap.recent_captures],
    )


@router.get(
    "/monitoring/blocking/stack_capture/diagnostics",
    response_model=StackCaptureDiagnosticsResponse,
)
async def runtime_stack_capture_diagnostics(
    engine: Annotated[BlockingStackCaptureEngine, Depends(get_stack_capture_engine)],
) -> StackCaptureDiagnosticsResponse:
    """Return the debug-grade stack-capture engine view.

    Adds backpressure pending/denied counters and the (opt-in) trace
    ring on top of the lean snapshot. The trace ring is empty unless
    ``trace_enabled=True``.
    """
    return StackCaptureDiagnosticsResponse(**engine.diagnostics_snapshot().to_dict())


@router.post(
    "/monitoring/blocking/stack_capture/manual",
    response_model=dict,
)
async def runtime_stack_capture_manual(
    payload: StackCaptureManualRequest,
    engine: Annotated[BlockingStackCaptureEngine, Depends(get_stack_capture_engine)],
) -> dict:
    """Operator-triggered stack capture. Bypasses the policy.

    Returns the captured stack's JSON payload, or an explanatory error
    when the engine is disabled / not running.
    """
    if not engine.is_running:
        raise HTTPException(status_code=409, detail="stack-capture engine is not running")
    stack = engine.capture_manual(
        trigger=payload.trigger,
        severity=payload.severity.upper() or "NONE",
        window_id=payload.window_id,
        sample_index=payload.sample_index,
    )
    if stack is None:
        raise HTTPException(status_code=409, detail="stack capture not produced (engine disabled?)")
    return stack.to_dict()


class BlockingWarningEmitterResponse(BaseModel):
    """Lean blocking-warning-emitter snapshot."""

    runtime_id: str
    state: str
    generated_at_monotonic_ns: int
    configuration: dict
    statistics: dict
    metrics: dict
    active_groups: list[dict]
    recent_groups: list[dict]


class BlockingWarningEmitterDiagnosticsResponse(BaseModel):
    """Debug-grade emitter view (trace + backpressure)."""

    state: str
    configuration: dict
    statistics: dict
    metrics: dict
    active_groups: list[dict]
    recent_groups: list[dict]
    backpressure: dict
    trace: dict


@router.get(
    "/warnings/blocking",
    response_model=BlockingWarningEmitterResponse,
)
async def runtime_blocking_warnings(
    emitter: Annotated[BlockingWarningEmitter, Depends(get_blocking_warning_emitter)],
) -> BlockingWarningEmitterResponse:
    """Return the canonical blocking-warning emitter snapshot.

    Includes active + recent warning groups (one per freeze window),
    lifetime statistics (groups seen, longest freeze, top coroutines),
    and engine self-metrics. Pair with
    ``/api/runtime/monitoring/blocking`` for the raw detector view and
    ``/api/runtime/monitoring/blocking/stack_capture`` for the captures
    that correlate to each group.
    """
    snap = emitter.snapshot()
    return BlockingWarningEmitterResponse(
        runtime_id=snap.runtime_id,
        state=snap.state,
        generated_at_monotonic_ns=snap.generated_at_monotonic_ns,
        configuration=snap.configuration,
        statistics=snap.statistics.to_dict(),
        metrics=snap.metrics.to_dict(),
        active_groups=[g.to_dict() for g in snap.active_groups],
        recent_groups=[g.to_dict() for g in snap.recent_groups],
    )


@router.get(
    "/warnings/blocking/diagnostics",
    response_model=BlockingWarningEmitterDiagnosticsResponse,
)
async def runtime_blocking_warnings_diagnostics(
    emitter: Annotated[BlockingWarningEmitter, Depends(get_blocking_warning_emitter)],
) -> BlockingWarningEmitterDiagnosticsResponse:
    """Return the debug-grade blocking-warning emitter view.

    Adds backpressure pending/denied + the (opt-in) trace ring. The
    trace ring is empty unless ``trace_enabled=True``.
    """
    return BlockingWarningEmitterDiagnosticsResponse(**emitter.diagnostics_snapshot().to_dict())


@router.post(
    "/warnings/blocking/sweep_expirations",
    response_model=dict,
)
async def runtime_blocking_warnings_sweep_expirations(
    emitter: Annotated[BlockingWarningEmitter, Depends(get_blocking_warning_emitter)],
) -> dict:
    """Operator-triggered expiration sweep.

    Promotes any RECOVERED group whose TTL has elapsed to EXPIRED and
    emits the corresponding event. The lifespan heartbeat does this
    automatically, but operators can demand an immediate sweep from
    diagnostics tooling.
    """
    expired = emitter.sweep_expirations()
    return {"expired": expired}
