/**
 * Internal store types.
 *
 * The store stores backend types (``TaskSnapshot``,
 * ``ActiveWarning``, ``TimelineSegment``) verbatim where the wire
 * shape is already normalized. Anything composite — connection
 * metadata, replay cursor, reconciliation stats — gets its own
 * dataclass-style interface here.
 */

import type {
  ActiveTimelineSegment,
  ActiveWarning,
  ClockSnapshot,
  ConnectionState,
  QueueSnapshot,
  RuntimeMetricsAggregateSnapshot,
  RuntimeStatus,
  TaskLifecycleEvent,
  TaskLifecycleState,
  TimelineSegment,
} from "@/types/runtime";
import type { ConnectionPhase } from "@/runtime/websocket";

/** Set of every task state the frontend tracks. */
export const TASK_STATES: readonly TaskLifecycleState[] = [
  "created",
  "running",
  "waiting",
  "completed",
  "cancelled",
  "failed",
] as const;

/** Set of terminal states — used by the regression guard. */
export const TERMINAL_TASK_STATES = new Set<TaskLifecycleState>([
  "completed",
  "cancelled",
  "failed",
]);

export interface ConnectionMeta {
  /** Phase reported by :class:`RuntimeWebSocketClient`. */
  phase: ConnectionPhase;
  /** Legacy projection used by existing UI. */
  state: ConnectionState;
  /** Reconnect attempts since the last clean start. */
  reconnectAttempts: number;
  /** Wall-clock monotonic ms when the last frame arrived. */
  lastFrameAtMonotonicMs: number;
}

/** Replay-mode discrete playback states the SPA mirrors from the
 *  backend's ``replay_status`` envelope. Same shape as
 *  :type:`ReplayPlaybackState` in the replay-timeline models, but
 *  duplicated here so the runtime store stays free of replay-package
 *  imports. */
export type RuntimeReplayPlaybackState =
  "idle" | "playing" | "paused" | "seeking" | "buffering" | "stopped" | "failed";

export interface RuntimeMeta {
  /** ``runtime_id`` from the most recent snapshot. */
  runtimeId: string | null;
  /** Latest server-reported status (idle / running / paused / stopped). */
  status: RuntimeStatus;
  /** Heartbeat-supplied uptime, in seconds. */
  serverUptimeSeconds: number;
  /** Heartbeat-supplied connected-client count. */
  connectedClients: number;
  /** Most recent :class:`ClockSnapshot`. */
  clock: ClockSnapshot | null;
  /**
   * ``true`` once a ``replay_status`` envelope has been observed.
   * Stays true for the lifetime of the connection — replay-mode is
   * a per-session property, not a per-frame one. The header reads
   * this to decide between the LIVE / REPLAY label families.
   */
  replayActive: boolean;
  /**
   * Last observed replay playback state (or ``null`` for live mode /
   * pre-handshake). Drives the PAUSED / STOPPED label overrides in
   * the connection projection.
   */
  replayPlaybackState: RuntimeReplayPlaybackState | null;
}

/**
 * All-fields-zero :type:`RuntimeMeta` baseline. Exported so the
 * store + every consumer that needs to construct a mock
 * (selector tests, harness fixtures) reads from a single source of
 * truth — adding a new field updates one line here and every test
 * picks it up.
 */
export const INITIAL_RUNTIME_META: RuntimeMeta = {
  runtimeId: null,
  status: "idle",
  serverUptimeSeconds: 0,
  connectedClients: 0,
  clock: null,
  replayActive: false,
  replayPlaybackState: null,
};

export interface ReplayMeta {
  /** Lowest sequence the backend can still satisfy via replay buffer. */
  oldestRetainedSequence: number | null;
  /** Highest sequence the backend can satisfy. */
  newestRetainedSequence: number | null;
  /** Whether the latest snapshot's ``since_sequence`` query hit retention. */
  windowHit: boolean;
}

export interface ReconciliationStats {
  envelopesApplied: number;
  duplicatesDropped: number;
  staleDropped: number;
  regressionsSuppressed: number;
  metricsDeltasApplied: number;
  warningDeltasApplied: number;
  timelineDeltasApplied: number;
  protocolErrors: number;
  hydrations: number;
  /** Last hydration duration in ms — used by the diagnostics page. */
  lastHydrationDurationMs: number;
  /**
   * Histogram of accepted ``runtime_event`` envelopes keyed by category
   * (the ``namespace.subsystem`` prefix of ``event_type`` — e.g.
   * ``"asyncio.task"``, ``"asyncio.queue"``, ``"asyncio.gather"``,
   * ``"runtime.metric"``). Lets the Diagnostics page render a per-
   * subsystem activity histogram without each consumer having to
   * maintain its own counter.
   */
  runtimeEventsByCategory: Record<string, number>;
  /**
   * Count of ``runtime_event`` envelopes whose ``payload.event_type``
   * was missing, non-string, or otherwise unparseable. A non-zero
   * value here is always a wire-protocol regression and surfaces a
   * concrete number for the diagnostics page rather than failing
   * silently.
   */
  unhandledRuntimeEvents: number;
}

/**
 * All-zero :type:`ReconciliationStats` baseline. Exported so the store
 * + every consumer that needs to construct a mock stats object
 * (tests, fixtures) reads from a single source of truth — adding a
 * new field updates one line here and every consumer picks it up.
 */
export const INITIAL_RECONCILIATION_STATS: ReconciliationStats = {
  envelopesApplied: 0,
  duplicatesDropped: 0,
  staleDropped: 0,
  regressionsSuppressed: 0,
  metricsDeltasApplied: 0,
  warningDeltasApplied: 0,
  timelineDeltasApplied: 0,
  protocolErrors: 0,
  hydrations: 0,
  lastHydrationDurationMs: 0,
  runtimeEventsByCategory: {},
  unhandledRuntimeEvents: 0,
};

export interface NormalizedTimelineState {
  /** Closed segments keyed by their ``segment_id``. */
  segmentsById: Record<string, TimelineSegment>;
  /** Active (still-open) segment per task. */
  activeSegmentsByTaskId: Record<string, ActiveTimelineSegment>;
  /** Ordered segment ids per task; oldest first. */
  segmentIdsByTaskId: Record<string, string[]>;
  /** Highest sequence applied to the timeline projection. */
  lastSequence: number;
}

export interface NormalizedWarningState {
  warningsById: Record<string, ActiveWarning>;
  activeWarningIds: string[];
  resolvedWarningIds: string[];
  countsBySeverity: {
    info: number;
    warning: number;
    error: number;
    critical: number;
  };
}

export interface NormalizedMetricsState {
  /** Full aggregate snapshot from the last hydration / refresh. */
  aggregate: RuntimeMetricsAggregateSnapshot | null;
  /** Rolling delta counters folded into the snapshot's counts. */
  deltaCounts: Record<string, number>;
}

export interface QueueMeta {
  /** Latest queue snapshot embedded in a runtime_snapshot. */
  queue: QueueSnapshot | null;
}

export type RuntimeEventEntry = TaskLifecycleEvent;

/**
 * Trace-line shape for the central ``runtime_event`` observability
 * ring buffer.
 *
 * The buffer is bounded (see ``RECENT_RUNTIME_EVENT_LIMIT`` in
 * ``store.ts``) and is keyed by sequence; it is **not** a feature
 * projection. Feature stores (queues, executors, semaphores,
 * dependencies) continue to subscribe to the websocket client
 * directly via :func:`client.subscribe("runtime_event", ...)` and
 * own their per-subsystem normalization.
 *
 * Why store the raw payload? A diagnostics consumer that wants to
 * dump "the last 200 backend events the dashboard saw" needs every
 * field that came over the wire; throwing them away here would mean
 * every future debug surface has to re-derive them from a feature
 * store. The buffer is sequence-bounded, so the memory footprint is
 * O(1).
 */
export interface RecentRuntimeEventEntry {
  /** Envelope sequence — monotonic per connection lifetime. */
  sequence: number | null;
  /** ``payload.event_type`` if present, else ``"unknown"``. */
  eventType: string;
  /** ``namespace.subsystem`` prefix, used as the histogram bucket. */
  category: string;
  /** Wall-clock seconds from the envelope, for timestamping the trace. */
  timestamp: number;
  /** Best-effort task id (most backend events carry one). */
  taskId: string | null;
  /** Raw payload — preserved verbatim for diagnostics deep-dives. */
  payload: Record<string, unknown>;
}

export interface DiagnosticsTrace {
  kind: "snapshot" | "delta" | "drop" | "selection";
  detail: string;
  at: number;
}
