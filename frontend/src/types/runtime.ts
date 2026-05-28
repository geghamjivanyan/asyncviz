// Snake_case field names mirror the backend protocol 1:1 so there's no
// transformation layer between the wire format and the store. Drift here =
// CI failure on either side; deliberate.

export type ConnectionState = "idle" | "connecting" | "open" | "closed" | "error";

export type RuntimeStatus = "idle" | "running" | "paused" | "stopped";

export type TaskLifecycleState =
  | "created"
  | "running"
  | "waiting"
  | "completed"
  | "cancelled"
  | "failed";

export interface TaskSnapshot {
  task_id: string;
  state: TaskLifecycleState;
  created_at: number;
  updated_at: number;
  asyncio_task_id: number | null;
  coroutine_name: string | null;
  task_name: string | null;
  parent_task_id: string | null;
  /** Lineage: topmost ancestor (own id when root). Mirrors the backend tracker. */
  root_task_id: string | null;
  /** Lineage: distance to root. 0 for roots; 1 for direct children; ... */
  depth: number;
  /** Lineage: closest-first chain of ancestor ids (empty for roots). */
  ancestor_chain: string[];
  /** Lineage: number of direct children currently tracked. */
  child_count: number;
  completed_at: number | null;
  duration_seconds: number | null;
  exception_type: string | null;
  exception_message: string | null;
  cancellation_origin: string | null;
  runtime_id: string | null;
  tags: Record<string, string>;
  metadata: Record<string, unknown>;
}

/** Mirrors the backend ``LineageSnapshot`` for the ``/api/runtime/lineage/{id}`` endpoint. */
export interface TaskLineageSnapshot {
  task_id: string;
  parent_task_id: string | null;
  root_task_id: string;
  depth: number;
  ancestor_chain: string[];
  child_count: number;
  descendants: string[];
}

export interface TasksResponse {
  tasks: TaskSnapshot[];
  total: number;
  active: number;
}

// ── WebSocket envelope ─────────────────────────────────────────────────────

export type EnvelopeType =
  | "heartbeat"
  | "system_status"
  | "runtime_snapshot"
  | "runtime_event"
  | "metrics_delta"
  | "warning_delta"
  | "timeline_delta"
  | "protocol_error"
  | "replay_status";

export interface RuntimeEnvelope<P = Record<string, unknown>> {
  protocol_version: string;
  type: EnvelopeType;
  timestamp: number;
  sequence?: number | null;
  payload: P;
}

/**
 * Streaming-engine wire payload for ``metrics_delta`` envelopes. The
 * frontend folds ``changes`` into the locally-cached aggregate snapshot;
 * full-snapshot consumers still call ``/api/runtime/aggregate``.
 */
export interface MetricsDeltaPayload {
  event_type: string;
  event_id: string;
  sequence: number | null;
  last_sequence: number;
  monotonic_ns: number;
  wall_seconds: number;
  changes: Record<string, number>;
  duration_added_seconds: number | null;
  coroutine_name: string | null;
  terminal_state: string | null;
}

/**
 * Streaming-engine wire payload for ``warning_delta`` envelopes. Mirrors
 * the backend ``WarningDeltaModel`` field-for-field.
 */
export interface WarningDeltaPayload {
  change: "activated" | "updated" | "deduplicated" | "resolved" | "expired";
  sequence: number | null;
  last_sequence: number;
  warning: ActiveWarning;
}

/**
 * Kind tag on ``timeline_delta`` envelopes. Mirrors backend
 * ``TimelineDeltaKind``. ``segment_opened`` carries an ``open_segment``,
 * ``segment_closed`` carries a finalized ``segment``, ``span_finalized``
 * carries a ``terminal_state``.
 */
export type TimelineDeltaKind = "segment_opened" | "segment_closed" | "span_finalized";

export interface TimelineDeltaPayload {
  kind: TimelineDeltaKind;
  task_id: string;
  sequence: number | null;
  monotonic_ns: number;
  wall_seconds: number;
  closed_a_segment: boolean;
  segment?: TimelineSegment;
  open_segment?: ActiveTimelineSegment;
  terminal_state?: string | null;
}

/**
 * Wire payload for ``protocol_error`` envelopes. Mirrors the canonical
 * REST :class:`APIErrorResponse` shape so the frontend can handle errors
 * uniformly across HTTP + websocket transports.
 */
export interface ProtocolErrorPayload {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export interface RuntimeSnapshotPayload {
  protocol_version: string;
  last_sequence: number;
  tasks: TaskSnapshot[];
  metrics: Record<string, number | null>;
  /**
   * Canonical clock view at the moment the snapshot was captured.
   * Optional for backward compatibility with pre-1.10 servers.
   */
  clock?: ClockSnapshot | null;
  /**
   * InternalEventQueue snapshot — capacity, depth, retention window, metrics.
   * Optional for backward compatibility with pre-1.11 servers.
   */
  queue?: QueueSnapshot | null;
  /**
   * RuntimeStateStore snapshot — projections omitted on the wire for size,
   * full version is available via /api/runtime/state. Optional for backward
   * compatibility with pre-2.1 servers.
   */
  state?: RuntimeStateSnapshot | null;
}

/**
 * Mirrors the backend ``RuntimeStateSnapshot`` (Pydantic) exactly. Field
 * names and types are part of the public protocol — drift surfaces in CI
 * (Pydantic uses ``extra='forbid'`` and TS uses strict).
 */
export interface RuntimeStateSnapshot {
  schema_version: number;
  generated_at: number;
  generated_at_monotonic_ns: number;
  last_sequence: number;
  last_event_id: string | null;
  runtime_id: string;
  tasks: TaskSnapshot[];
  task_ids_by_state: Record<string, string[]>;
  metrics: {
    total_tasks: number;
    active_tasks: number;
    completed_tasks: number;
    cancelled_tasks: number;
    failed_tasks: number;
    terminal_tasks: number;
    average_duration_seconds: number | null;
    cancellations_by_origin: Record<string, number>;
    rejected_transitions: number;
  };
  lineage: {
    tracked_tasks: number;
    root_tasks: number;
    max_depth: number;
    orphan_links: number;
    cyclic_rejections: number;
    roots: string[];
  };
  projections: Record<string, unknown>;
  /**
   * Per-task lifecycle history (task_id → ordered list of transitions).
   * Each transition mirrors the backend ``TransitionRecord`` shape.
   */
  transitions: Record<string, TaskTransitionRecord[]>;
}

/**
 * Mirrors the backend ``TransitionRecord``: a single step in a task's
 * lifecycle, stamped by the reducer that handled the corresponding event.
 * ``sequence`` may be ``null`` when an event was applied without a queue
 * sequence (e.g. tests, replay tools).
 */
export interface TaskTransitionRecord {
  sequence: number | null;
  state: TaskLifecycleState;
  monotonic_ns: number;
  wall_seconds: number;
  event_id: string;
  event_type: string;
}

// ── Timeline payload taxonomy ──────────────────────────────────────────────

/**
 * Mirrors the backend ``TimelineSegment`` Pydantic exactly. One finalized
 * execution interval on a task's timeline.
 */
export interface TimelineSegment {
  task_id: string;
  segment_id: string;
  segment_type: "run" | "wait";
  sequence_start: number | null;
  sequence_end: number | null;
  monotonic_start_ns: number;
  monotonic_end_ns: number;
  duration_ns: number;
  wall_start: number;
  wall_end: number;
  state: string;
  parent_task_id: string | null;
  coroutine_name: string | null;
  task_name: string | null;
  metadata: Record<string, unknown>;
}

/** JSON-safe view of an open (still-running) segment. */
export interface ActiveTimelineSegment {
  task_id: string;
  segment_id: string;
  segment_type: "run" | "wait";
  sequence_start: number | null;
  monotonic_start_ns: number;
  wall_start: number;
  state: string;
  parent_task_id: string | null;
  coroutine_name: string | null;
  task_name: string | null;
}

/** Aggregate view of a task's whole lifetime on the timeline. */
export interface LifecycleSpan {
  task_id: string;
  parent_task_id: string | null;
  coroutine_name: string | null;
  task_name: string | null;
  created_at_monotonic_ns: number;
  created_at_wall: number;
  terminated_at_monotonic_ns: number | null;
  terminated_at_wall: number | null;
  terminal_state: string | null;
  total_duration_ns: number;
  run_duration_ns: number;
  wait_duration_ns: number;
  segment_count: number;
  segments: TimelineSegment[];
  active_segment: ActiveTimelineSegment | null;
  depth: number;
  root_task_id: string | null;
}

/** A vertical lane containing one or more spans. */
export interface TimelineTrack {
  track_id: string;
  track_type: "task" | "root" | "coroutine";
  label: string;
  spans: LifecycleSpan[];
  earliest_monotonic_ns: number;
  latest_monotonic_ns: number;
}

/**
 * Canonical timeline snapshot. Mirrors the backend ``TimelineSnapshot``
 * Pydantic field-for-field.
 */
export interface TimelineSnapshot {
  schema_version: number;
  generated_at: number;
  generated_at_monotonic_ns: number;
  runtime_id: string;
  last_sequence: number;
  tracks: TimelineTrack[];
  spans_by_task: Record<string, LifecycleSpan>;
  active_segments: ActiveTimelineSegment[];
  metrics: Record<string, unknown>;
}

// ── Metrics aggregator payload taxonomy ─────────────────────────────────────

/** Mirrors the backend ``HistogramModel``. */
export interface HistogramModel {
  count: number;
  min_value: number;
  max_value: number;
  mean: number;
  p50: number;
  p95: number;
  p99: number;
  sum_value: number;
  samples: number;
}

/** Mirrors the backend ``DurationStatsModel``. */
export interface DurationStatsModel {
  count: number;
  total_seconds: number;
  min_seconds: number;
  max_seconds: number;
  mean_seconds: number;
  histogram: HistogramModel;
}

/** Mirrors the backend ``DurationsByStateModel``. */
export interface DurationsByStateModel {
  completed: DurationStatsModel;
  cancelled: DurationStatsModel;
  failed: DurationStatsModel;
  overall: DurationStatsModel;
}

/** Mirrors the backend ``TaskCountsModel``. */
export interface TaskCountsModel {
  total: number;
  active: number;
  waiting: number;
  completed: number;
  cancelled: number;
  failed: number;
  terminal: number;
}

/** Mirrors the backend ``ThroughputModel``. */
export interface ThroughputModel {
  tasks_per_second: number;
  completions_per_second: number;
  cancellations_per_second: number;
  failures_per_second: number;
  window_seconds: number;
}

/** Mirrors the backend ``CoroutineRowModel``. */
export interface CoroutineRowModel {
  coroutine_name: string;
  task_count: number;
  active_count: number;
  completed_count: number;
  cancelled_count: number;
  failed_count: number;
  completed_total_duration_seconds: number;
  completed_avg_duration_seconds: number | null;
  max_duration_seconds: number | null;
}

/** Mirrors the backend ``LineageMetricsModel``. */
export interface LineageMetricsModel {
  root_count: number;
  max_depth: number;
  average_fanout: number;
  largest_tree_size: number;
  largest_tree_root_id: string | null;
  cancellations_propagated: number;
}

/** Mirrors the backend ``TopTaskModel``. */
export interface TopTaskModel {
  task_id: string;
  coroutine_name: string | null;
  task_name: string | null;
  duration_seconds: number;
  state: string;
}

/** Mirrors the backend ``TimelineSummaryModel``. */
export interface TimelineSummaryModel {
  transitions_applied: number;
  transitions_rejected: number;
  segments_opened: number;
  segments_closed: number;
  segments_by_type: Record<string, number>;
  invalid_transitions: number;
  active_segments: number;
  finalized_spans: number;
}

/** Mirrors the backend ``AggregatorSelfMetricsModel``. */
export interface AggregatorSelfMetricsModel {
  events_observed: number;
  events_stale: number;
  events_duplicate: number;
  snapshots_emitted: number;
  rebuilds_completed: number;
  subscription_dispatches: number;
  subscription_failures: number;
  last_event_sequence: number;
}

// ── WebSocket gateway observability ────────────────────────────────────────

/** Mirrors the backend ``GatewaySessionsByState`` Pydantic. */
export interface GatewaySessionsByState {
  pending: number;
  hydrating: number;
  live: number;
  draining: number;
  closed: number;
}

/** Mirrors the backend ``GatewaySessionMetricsModel`` Pydantic. */
export interface GatewaySessionMetricsModel {
  messages_sent: number;
  messages_dropped: number;
  heartbeats_sent: number;
  heartbeats_missed: number;
  send_failures: number;
  bytes_sent: number;
  backpressure_events: number;
}

/** Mirrors the backend ``GatewayMetricsResponse`` Pydantic. */
export interface GatewayMetricsResponse {
  sessions_opened: number;
  sessions_closed: number;
  sessions_active: number;
  handshake_replay_hits: number;
  handshake_replay_misses: number;
  handshake_snapshot_hydrations: number;
  messages_sent: number;
  messages_dropped: number;
  heartbeats_sent: number;
  sessions_stale_evicted: number;
  protocol_errors: number;
  sessions_by_state: GatewaySessionsByState;
  aggregate_session_metrics: GatewaySessionMetricsModel;
}

/**
 * Canonical lifecycle states for the shutdown coordinator. Mirrors
 * the backend ``ShutdownPhase`` StrEnum field-for-field.
 *
 * Phases are monotonic — every shutdown advances through these in
 * order. Dashboards read the current phase to decide whether to
 * render a shutdown banner, retry-with-backoff, or fail-permanently.
 */
export type ShutdownPhase = "idle" | "draining" | "finalizing" | "stopping" | "stopped" | "failed";

/** One :class:`PhaseTiming` on the wire. */
export interface PhaseTimingPayload {
  phase: ShutdownPhase;
  duration_ns: number;
  timed_out: boolean;
}

/**
 * Post-shutdown report. Available once the coordinator reaches a
 * terminal phase. Surfaces the structured timeline of what happened
 * (per-phase durations, timeout count, forced disconnects/cancellations,
 * final replay checkpoint + snapshot ids).
 */
export interface ShutdownReportPayload {
  final_phase: ShutdownPhase;
  reason: string;
  triggered_at_monotonic_ns: number;
  finished_at_monotonic_ns: number;
  total_duration_ns: number;
  phase_timings: PhaseTimingPayload[];
  timeouts_total: number;
  forced_disconnects: number;
  forced_cancellations: number;
  checkpoint_id: string | null;
  snapshot_id: string | null;
  final_sequence: number | null;
  errors: string[];
}

/**
 * Output of ``GET /api/runtime/shutdown``. Polled by dashboards to
 * render the shutdown banner / reconnect guidance. ``report`` is only
 * populated once the coordinator has reached a terminal phase.
 */
export interface ShutdownStatusResponse {
  protocol_version: number;
  phase: ShutdownPhase;
  requested: boolean;
  in_progress: boolean;
  completed: boolean;
  report: ShutdownReportPayload | null;
}

/**
 * Mirrors the backend ``ShutdownMetricsResponse`` Pydantic. Returned
 * by ``GET /api/runtime/shutdown/metrics``; cumulative counters across
 * the process lifetime (the dashboard can be started/stopped multiple
 * times in long-running embeddings).
 */
export interface ShutdownMetricsResponse {
  current_phase: ShutdownPhase;
  shutdowns_requested: number;
  shutdowns_completed: number;
  shutdowns_failed: number;
  timeouts_total: number;
  forced_disconnects: number;
  forced_cancellations: number;
  last_total_duration_ns: number;
  max_total_duration_ns: number;
}

/**
 * One entry in the resolved frontend build manifest. Mirrors the
 * backend ``ManifestEntry`` / ``FrontendManifestEntry`` model.
 */
export interface FrontendManifestEntry {
  file: string;
  name: string;
  is_entry: boolean;
  css: string[];
}

/**
 * Output of ``GET /api/runtime/frontend``. Operationally useful
 * inventory of what the static-frontend layer is actually serving:
 * configured mode, on-disk static directory, bundle presence, asset
 * count + total size, primary entry module, linked CSS, and the build
 * manifest (Vite-emitted or filesystem-discovered).
 *
 * Frontend bootstrap code can use ``entry_module`` / ``entry_css`` to
 * inject hydration data tied to the current build; operators read
 * ``manifest_source`` to confirm the manifest is real (``"vite"``)
 * vs. synthetic (``"scan"``).
 */
export interface FrontendInfoResponse {
  protocol_version: number;
  mode: string;
  static_dir: string;
  bundle_present: boolean;
  assets_dir_present: boolean;
  asset_count: number;
  asset_size_bytes: number;
  entry_module: string | null;
  entry_css: string[];
  manifest_source: string;
  manifest_entries: FrontendManifestEntry[];
}

/**
 * Mirrors the backend ``FrontendServingMetricsResponse`` Pydantic.
 * Returned by ``GET /api/runtime/frontend/metrics``; tracks asset
 * hits / misses, SPA fallback hits, reserved-prefix blocks,
 * path-traversal blocks, and manifest-load outcomes.
 */
export interface FrontendServingMetricsResponse {
  asset_requests: number;
  asset_hits: number;
  asset_misses: number;
  immutable_hits: number;
  loose_hits: number;
  index_served: number;
  spa_fallbacks: number;
  reserved_blocked: number;
  path_traversal_blocked: number;
  manifest_loads: number;
  manifest_load_failures: number;
}

/**
 * Canonical operational health status. Mirrors the backend
 * ``HealthStatus`` StrEnum field-for-field. The dashboard's status
 * badge maps these values to colors.
 */
export type HealthStatus = "healthy" | "degraded" | "starting" | "stopping" | "unavailable";

/**
 * Probe severity. ``critical`` failures drag the runtime to
 * ``UNAVAILABLE``; ``info`` failures stop at ``DEGRADED``.
 */
export type CheckSeverity = "critical" | "info";

/** One probe's result on the wire. */
export interface HealthCheckPayload {
  name: string;
  status: HealthStatus;
  severity: CheckSeverity;
  message: string;
  latency_ns: number;
  details: Record<string, unknown>;
}

/**
 * Output of ``GET /api/health/live``. Cheapest probe — the existence
 * of a 200 response is proof the process is alive.
 */
export interface LivenessSnapshot {
  status: HealthStatus;
  protocol_version: number;
  generated_at: number;
  generated_at_monotonic_ns: number;
  process_uptime_seconds: number;
}

/**
 * Output of ``GET /api/health/ready``. ``status`` is aggregated from
 * the CRITICAL probes; ``HEALTHY`` / ``DEGRADED`` mean the response
 * was 200, anything else means 503.
 */
export interface ReadinessSnapshot {
  status: HealthStatus;
  protocol_version: number;
  generated_at: number;
  generated_at_monotonic_ns: number;
  runtime_id: string;
  runtime_status: string;
  runtime_uptime_seconds: number;
  critical_checks: HealthCheckPayload[];
  degraded_count: number;
  unavailable_count: number;
}

/**
 * Output of ``GET /api/health``. The canonical aggregated summary —
 * every probe's result + a precomputed bucket summary.
 */
export interface HealthSnapshot {
  status: HealthStatus;
  protocol_version: number;
  generated_at: number;
  generated_at_monotonic_ns: number;
  runtime_id: string;
  runtime_status: string;
  runtime_uptime_seconds: number;
  evaluation_duration_ns: number;
  checks: HealthCheckPayload[];
  summary: Record<string, number>;
}

/**
 * Output of ``GET /api/health/runtime``. Aggregated status + every
 * probe + per-subsystem operational counters. Powers the dashboard's
 * diagnostics panel.
 */
export interface RuntimeDiagnosticsSnapshot {
  status: HealthStatus;
  protocol_version: number;
  generated_at: number;
  generated_at_monotonic_ns: number;
  runtime_id: string;
  runtime_status: string;
  runtime_uptime_seconds: number;
  process_uptime_seconds: number;
  tasks_total: number;
  tasks_active: number;
  tasks_terminal: number;
  queue_depth: number;
  queue_capacity: number;
  queue_dropped_overflow: number;
  replay_frame_count: number;
  replay_oldest_sequence: number | null;
  replay_newest_sequence: number | null;
  replay_misses: number;
  websocket_active_sessions: number;
  websocket_protocol_errors: number;
  streaming_running: boolean;
  streaming_broadcast_failures: number;
  snapshot_average_generation_ns: number;
  snapshot_max_generation_ns: number;
  warnings_active: number;
  warnings_critical: number;
  warnings_error: number;
  warnings_warning: number;
  warnings_info: number;
  checks: HealthCheckPayload[];
  summary: Record<string, number>;
}

/**
 * Mirrors the backend ``HealthServiceMetricsResponse`` Pydantic.
 * Returned by ``GET /api/health/metrics``; tracks how often each
 * probe surface is called, the rate of degraded/unavailable
 * evaluations, total probe failures, and evaluation timings.
 */
export interface HealthServiceMetricsResponse {
  evaluations_total: number;
  liveness_checks: number;
  readiness_checks: number;
  full_checks: number;
  runtime_diagnostics_calls: number;
  degraded_evaluations: number;
  unavailable_evaluations: number;
  probe_failures: number;
  total_evaluation_ns: number;
  average_evaluation_ns: number;
  max_evaluation_ns: number;
  last_evaluation_ns: number;
}

/**
 * Canonical hydration envelope returned by ``GET /api/runtime/snapshot``.
 * Composes the existing sub-snapshots under one consistency cursor —
 * frontend hydration code reads ``metadata`` + ``consistency`` first to
 * validate compatibility (``runtime_id``, ``snapshot_version``) and then
 * dispatches each ``*`` field to the relevant store.
 *
 * Each ``*`` field is the same type the corresponding ``/api/runtime/<x>``
 * endpoint returns — no parallel deserialization is needed.
 */
export interface RuntimeSnapshot {
  metadata: SnapshotMetadata;
  consistency: SnapshotConsistency;
  clock: ClockSnapshot;
  state: RuntimeStateSnapshot | null;
  timeline: TimelineSnapshot | null;
  metrics: RuntimeMetricsAggregateSnapshot | null;
  warnings: WarningSnapshot | null;
  replay: ReplaySnapshot | null;
  queue: QueueSnapshot | null;
  hints: Record<string, unknown>;
}

/**
 * Snapshot envelope metadata. ``snapshot_version`` is the protocol version
 * — bumped on incompatible shape changes. Sub-snapshots carry their own
 * ``schema_version`` for fine-grained evolution.
 *
 * ``included_sources`` / ``skipped_sources`` reflect the
 * :class:`HydrationOptions` toggles the request used; frontend code that
 * needs a missing sub-snapshot should refetch with the right filter
 * instead of silently failing.
 */
export interface SnapshotMetadata {
  snapshot_version: number;
  snapshot_id: string;
  runtime_id: string;
  generated_at: number;
  generated_at_monotonic_ns: number;
  generation_duration_ns: number;
  payload_bytes: number;
  is_full: boolean;
  included_sources: string[];
  skipped_sources: string[];
}

/**
 * Consistency cursor describing what the snapshot reflects. ``last_sequence``
 * is the cursor a client picks up streaming from after hydration — pair this
 * with the ``/ws`` ``since_sequence`` handshake to fold deltas without
 * divergence.
 *
 * ``replay_window_hit`` mirrors the canonical replay buffer ``covers()``
 * predicate: when false, a ``since_sequence`` provided to the snapshot
 * request cannot be reconstructed from retention, so the client should
 * treat this as a cold restart.
 */
export interface SnapshotConsistency {
  last_sequence: number;
  last_event_id: string | null;
  generated_at_monotonic_ns: number;
  generated_at: number;
  oldest_retained_sequence: number | null;
  newest_retained_sequence: number | null;
  replay_window_hit: boolean;
}

/**
 * Mirrors the backend ``RuntimeSnapshotMetricsResponse`` Pydantic. Returned by
 * ``GET /api/runtime/snapshot/metrics``; tracks generation counts, timings,
 * and payload sizes so operators can spot snapshots growing past their
 * latency budget.
 */
export interface RuntimeSnapshotMetricsResponse {
  snapshots_generated: number;
  full_snapshots: number;
  filtered_snapshots: number;
  total_generation_ns: number;
  average_generation_ns: number;
  max_generation_ns: number;
  last_generation_ns: number;
  last_payload_bytes: number;
  max_payload_bytes: number;
  sources_skipped: number;
  consistency_errors: number;
}

/**
 * Mirrors the backend ``StreamingMetricsResponse`` Pydantic. Returned by
 * ``GET /api/runtime/streaming``; counts per-stream broadcast totals plus
 * the subscription-dispatch / failure tally for the streaming engine.
 */
export interface StreamingMetricsResponse {
  running: boolean;
  metrics_deltas_sent: number;
  warning_deltas_sent: number;
  timeline_deltas_sent: number;
  runtime_deltas_sent: number;
  protocol_errors_sent: number;
  subscription_dispatches: number;
  subscription_failures: number;
  broadcast_failures: number;
}

// ── Backend self-observability ─────────────────────────────────────────────

/** Mirrors the backend ``BackendMetricsResponse`` Pydantic. */
export interface BackendMetricsResponse {
  requests_total: number;
  requests_in_flight: number;
  requests_by_status: Record<string, number>;
  requests_by_method: Record<string, number>;
  average_duration_ms: number;
  max_duration_ms: number;
  api_errors_total: number;
  api_errors_by_code: Record<string, number>;
  ws_connections_total: number;
  ws_disconnections_total: number;
  ws_active_connections: number;
}

/** Mirrors the canonical JSON error envelope (``error_response_payload``). */
export interface APIErrorResponse {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
    correlation_id: string | null;
    status_code: number;
  };
}

// ── Replay buffer payload taxonomy ─────────────────────────────────────────

/** Mirrors the backend ``ReplayFrameModel`` Pydantic. */
export interface ReplayFrameModel {
  sequence: number;
  event_id: string;
  event_type: string;
  monotonic_ns: number;
  wall_seconds: number;
  runtime_id: string;
  task_id: string | null;
  parent_task_id: string | null;
  payload: Record<string, unknown>;
}

/** Mirrors the backend ``ReplayWindowModel``. */
export interface ReplayWindowModel {
  requested_since: number;
  requested_end: number | null;
  hit: boolean;
  oldest_available_sequence: number | null;
  newest_available_sequence: number | null;
  frames: ReplayFrameModel[];
}

/** Mirrors the backend ``ReplayCheckpointModel``. */
export interface ReplayCheckpointModel {
  checkpoint_id: string;
  sequence: number;
  monotonic_ns: number;
  wall_seconds: number;
  runtime_id: string;
  state: Record<string, unknown> | null;
  timeline: Record<string, unknown> | null;
  metrics: Record<string, unknown> | null;
  warnings: Record<string, unknown> | null;
  label: string | null;
}

/** Mirrors the backend ``ReplayBatchModel`` — what reconnects receive. */
export interface ReplayBatchModel {
  window: ReplayWindowModel;
  checkpoint: ReplayCheckpointModel | null;
}

/** Mirrors the backend ``ReplaySelfMetricsModel``. */
export interface ReplaySelfMetricsModel {
  frames_appended: number;
  frames_evicted: number;
  replay_requests: number;
  replay_hits: number;
  replay_misses: number;
  checkpoints_created: number;
  reconstructions_completed: number;
  subscription_dispatches: number;
  subscription_failures: number;
}

/** Mirrors the backend ``ReplaySnapshot``. */
export interface ReplaySnapshot {
  schema_version: number;
  generated_at: number;
  generated_at_monotonic_ns: number;
  runtime_id: string;
  capacity: number;
  frame_count: number;
  oldest_sequence: number | null;
  newest_sequence: number | null;
  oldest_evicted_sequence: number | null;
  checkpoints: ReplayCheckpointModel[];
  latest_checkpoint: ReplayCheckpointModel | null;
  self_metrics: ReplaySelfMetricsModel;
}

// ── Runtime warnings payload taxonomy ───────────────────────────────────────

export type WarningSeverity = "info" | "warning" | "error" | "critical";

/** Mirrors the backend ``ActiveWarning`` Pydantic. */
export interface ActiveWarning {
  warning_id: string;
  warning_key: string;
  warning_type: string;
  severity: WarningSeverity;
  message: string;
  detector: string;
  created_sequence: number | null;
  created_monotonic_ns: number;
  created_at_wall: number;
  last_observed_sequence: number | null;
  last_observed_monotonic_ns: number;
  last_observed_wall: number;
  occurrence_count: number;
  resolved: boolean;
  resolved_sequence: number | null;
  resolved_monotonic_ns: number | null;
  resolved_at_wall: number | null;
  expired: boolean;
  related_task_ids: string[];
  lineage_root_id: string | null;
  metadata: Record<string, unknown>;
  runtime_id: string | null;
}

/** Mirrors the backend ``WarningSeverityCounts``. */
export interface WarningSeverityCounts {
  info: number;
  warning: number;
  error: number;
  critical: number;
}

/** Mirrors the backend ``WarningSelfMetricsModel``. */
export interface WarningSelfMetricsModel {
  detectors_registered: number;
  evaluations_run: number;
  detector_failures: number;
  warnings_emitted: number;
  warnings_resolved: number;
  warnings_expired: number;
  dedup_suppressions: number;
  snapshots_emitted: number;
  subscription_dispatches: number;
  subscription_failures: number;
  last_event_sequence: number;
}

/**
 * Canonical warnings snapshot. Mirrors the backend ``WarningSnapshot``
 * Pydantic field-for-field.
 */
export interface WarningSnapshot {
  schema_version: number;
  generated_at: number;
  generated_at_monotonic_ns: number;
  runtime_id: string;
  last_sequence: number;
  active: ActiveWarning[];
  resolved: ActiveWarning[];
  counts_by_severity: WarningSeverityCounts;
  counts_by_type: Record<string, number>;
  self_metrics: WarningSelfMetricsModel;
}

/**
 * Streaming delta. The change is one of the lifecycle transitions the
 * backend ``WarningChange`` StrEnum defines.
 */
export interface WarningDeltaModel {
  warning: ActiveWarning;
  change: "activated" | "updated" | "resolved" | "expired" | "deduplicated";
  sequence: number | null;
  last_sequence: number;
}

/**
 * Canonical analytics snapshot. Mirrors the backend
 * ``RuntimeMetricsAggregateSnapshot`` Pydantic field-for-field.
 */
export interface RuntimeMetricsAggregateSnapshot {
  schema_version: number;
  generated_at: number;
  generated_at_monotonic_ns: number;
  runtime_id: string;
  last_sequence: number;
  runtime_uptime_seconds: number;
  counts: TaskCountsModel;
  throughput: ThroughputModel;
  durations: DurationsByStateModel;
  coroutines: CoroutineRowModel[];
  lineage: LineageMetricsModel;
  cancellations_by_origin: Record<string, number>;
  longest_tasks: TopTaskModel[];
  shortest_tasks: TopTaskModel[];
  timeline: TimelineSummaryModel | null;
  self_metrics: AggregatorSelfMetricsModel;
}

/**
 * Mirrors the backend ``QueueSnapshotResponse`` exactly. ``oldest_retained_sequence``
 * is the lower bound for what a reconnect's ``since_sequence`` query can
 * recover; anything older requires falling back to a fresh runtime_snapshot.
 */
export interface QueueSnapshot {
  capacity: number;
  depth: number;
  overflow_strategy: string;
  retention_capacity: number;
  retained: number;
  oldest_retained_sequence: number | null;
  newest_retained_sequence: number | null;
  running: boolean;
  metrics: Record<string, number>;
}

/**
 * Mirrors the backend ``ClockSnapshot`` (Pydantic) exactly. ``monotonic_ns``
 * is the authoritative ordering primitive; ``current_sequence`` is the last
 * envelope sequence allocated by this clock.
 */
export interface ClockSnapshot {
  runtime_id: string;
  started_at_wall_seconds: number;
  started_at_monotonic_ns: number;
  wall_now_seconds: number;
  wall_now_iso: string;
  monotonic_now_ns: number;
  monotonic_now_seconds: number;
  uptime_seconds: number;
  uptime_ns: number;
  current_sequence: number;
}

// ── Runtime event payload taxonomy ─────────────────────────────────────────

export interface RuntimeEventBase {
  event_id: string;
  event_type: string;
  /** Wall-clock seconds (drift-safe; sourced from the canonical RuntimeClock). */
  timestamp: number;
  /** Monotonic seconds at event creation. */
  monotonic_timestamp: number;
  /** Same instant as ``monotonic_timestamp``, in integer nanoseconds. */
  monotonic_ns: number;
  runtime_id: string;
  source: string;
  payload_version: number;
}

interface TaskEventBase extends RuntimeEventBase {
  task_id: string;
  parent_task_id: string | null;
  coroutine_name: string | null;
  task_name: string | null;
  metadata: Record<string, unknown>;
}

export interface TaskCreatedEvent extends TaskEventBase {
  event_type: "asyncio.task.created";
}

export interface TaskStartedEvent extends TaskEventBase {
  event_type: "asyncio.task.started";
}

export interface TaskWaitingEvent extends TaskEventBase {
  event_type: "asyncio.task.waiting";
  reason: string | null;
}

export interface TaskResumedEvent extends TaskEventBase {
  event_type: "asyncio.task.resumed";
}

interface TerminalTaskEventBase extends TaskEventBase {
  created_at: number | null;
  completed_at: number | null;
  duration_seconds: number | null;
}

export interface TaskCompletedEvent extends TerminalTaskEventBase {
  event_type: "asyncio.task.completed";
}

export interface TaskCancelledEvent extends TerminalTaskEventBase {
  event_type: "asyncio.task.cancelled";
  cancellation_origin: string | null;
}

export interface TaskFailedEvent extends TerminalTaskEventBase {
  event_type: "asyncio.task.failed";
  exception_type: string | null;
  exception_message: string | null;
}

export type TaskLifecycleEvent =
  | TaskCreatedEvent
  | TaskStartedEvent
  | TaskWaitingEvent
  | TaskResumedEvent
  | TaskCompletedEvent
  | TaskCancelledEvent
  | TaskFailedEvent;

export interface HeartbeatPayload {
  server_uptime_seconds: number;
  connected_clients: number;
}

export interface RuntimeMetrics {
  events_emitted: number;
  websocket_messages_sent: number;
  /** Seconds since the canonical RuntimeClock was constructed. */
  runtime_uptime_seconds?: number;
  /** Highest sequence id allocated by the runtime clock so far. */
  sequence_issued?: number;
  /** Live depth of the internal event queue (gauge). */
  queue_depth?: number;
  /** Configured capacity of the internal event queue. */
  queue_capacity?: number;
  /** Lifetime publish count via the internal event queue. */
  queue_published?: number;
  /** Lifetime dispatch count via the internal event queue. */
  queue_dispatched?: number;
  /** Lifetime overflow drops (sum of drop_oldest + drop_newest + fail_fast). */
  queue_dropped_overflow?: number;
  /** Current retention buffer size (gauge). */
  queue_retained?: number;
  /** Lifetime replay hits — reconnects that got their gap streamed. */
  queue_replay_hits?: number;
  /** Lifetime replay misses — reconnects that fell back to snapshots. */
  queue_replay_misses?: number;
  /** Lineage: total tasks the tracker knows about (gauge). */
  lineage_tracked_tasks?: number;
  /** Lineage: tasks with no parent (gauge). */
  lineage_root_tasks?: number;
  /** Lineage: deepest ancestor chain currently observed (gauge). */
  lineage_max_depth?: number;
  /** Lineage: links to parents the registry doesn't know — observability for replay drift. */
  lineage_orphan_links?: number;
  /** Lineage: cyclic ancestry rejections — defensive counter, expected 0. */
  lineage_cyclic_rejections?: number;
  /** Timeline: transitions successfully applied to the segment engine. */
  timeline_transitions_applied?: number;
  /** Timeline: transitions rejected (invalid / terminal-locked / unknown). */
  timeline_transitions_rejected?: number;
  /** Timeline: lifetime segments opened (run + wait combined). */
  timeline_segments_opened?: number;
  /** Timeline: lifetime segments closed. */
  timeline_segments_closed?: number;
  /** Timeline: currently-open segments across all tasks (gauge). */
  timeline_active_segments?: number;
  /** Timeline: lifetime tasks that reached a terminal state. */
  timeline_finalized_spans?: number;
  /** Timeline: invalid-transition rejections (subset of transitions_rejected). */
  timeline_invalid_transitions?: number;
  /** Timeline: lifetime rebuild count. */
  timeline_rebuilds_completed?: number;
  /** State store: successful applies. */
  state_events_applied?: number;
  /** State store: stale-sequence rejections. */
  state_events_stale?: number;
  /** State store: duplicate event_id rejections. */
  state_events_duplicate?: number;
  /** State store: events with no reducer (warnings, metrics, etc). */
  state_events_unknown_type?: number;
  /** State store: applies that failed inside the reducer. */
  state_events_rejected?: number;
  /** State store: highest applied sequence (high-water mark). */
  state_last_sequence?: number;
  /** State store: lifetime ``store.snapshot()`` calls. */
  state_snapshots_emitted?: number;
  /** State store: lifetime listener notifications. */
  state_subscription_dispatches?: number;
}
