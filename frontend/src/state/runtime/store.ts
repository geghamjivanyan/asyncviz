/**
 * Canonical normalized runtime store.
 *
 * The store is composed from pure reducers + sequencing helpers. The
 * Zustand factory wires them into ``set()`` calls and exposes a small
 * surface of action methods:
 *
 *   * :meth:`hydrateSnapshot` — fold a :class:`RuntimeSnapshot` into
 *     every projection. Used by ``useHydrateRuntime`` after the
 *     websocket client's first hydration completes.
 *   * :meth:`applyEnvelope` — dispatch one websocket envelope through
 *     the matching reducer. Sequence-gated; duplicates + stale frames
 *     are dropped + counted in ``stats``.
 *   * :meth:`applyReplayBatch` — apply many envelopes in order; same
 *     semantics as :meth:`applyEnvelope` but with one ``set()`` call
 *     per envelope (Zustand batches at the React boundary).
 *   * :meth:`setConnection` — mirror the websocket client's phase +
 *     legacy connection-state projection.
 *   * :meth:`selectTask` — selection (UI state, not runtime state).
 *   * :meth:`clearEvents` — drop the ring buffer.
 *   * :meth:`reset` — full reset back to the initial state.
 */

import { create } from "zustand";
import type {
  ClockSnapshot,
  ConnectionState,
  HeartbeatPayload,
  MetricsDeltaPayload,
  QueueSnapshot,
  RuntimeEnvelope,
  RuntimeMetricsAggregateSnapshot,
  RuntimeSnapshot,
  RuntimeStateSnapshot,
  RuntimeStatus,
  TaskLifecycleEvent,
  TaskLifecycleState,
  TaskSnapshot,
  TimelineDeltaPayload,
  WarningDeltaPayload,
} from "@/types/runtime";
import type { ConnectionPhase } from "@/runtime/websocket";
import { toConnectionState } from "@/runtime/websocket";
import {
  isTaskLifecycleEvent,
  reduceHeartbeat,
  reduceMetricsDelta,
  reduceTaskEvent,
  reduceTimelineDelta,
  reduceWarningDelta,
  reindexTaskState,
} from "@/state/runtime/reducers";
import {
  normalizeTasks,
  normalizeTimeline,
  normalizeWarnings,
} from "@/state/runtime/normalization";
import { decideStoreSequence, maxSequence } from "@/state/runtime/sequencing";
import {
  INITIAL_RECONCILIATION_STATS,
  INITIAL_RUNTIME_META,
  type ConnectionMeta,
  type NormalizedMetricsState,
  type NormalizedTimelineState,
  type NormalizedWarningState,
  type QueueMeta,
  type RecentRuntimeEventEntry,
  type ReconciliationStats,
  type ReplayMeta,
  type RuntimeEventEntry,
  type RuntimeMeta,
} from "@/state/runtime/models";

const EVENT_BUFFER_LIMIT = 1000;
/**
 * Bounded ring buffer of the most recent ``runtime_event`` envelopes
 * the central reducer accepted (regardless of subsystem). Sized
 * smaller than the task-lifecycle ring because every backend event
 * lands here; 500 entries covers ~10 s of dense traffic from
 * sample_runtime at 50 events/sec.
 */
const RECENT_RUNTIME_EVENT_LIMIT = 500;

export interface RuntimeStoreState {
  // ── Connection / runtime / replay metadata ──────────────────────
  connection: ConnectionMeta;
  runtime: RuntimeMeta;
  replay: ReplayMeta;
  queue: QueueMeta;

  // ── Normalized projections ──────────────────────────────────────
  tasksById: Record<string, TaskSnapshot>;
  taskIdsByState: Record<TaskLifecycleState, string[]>;
  timeline: NormalizedTimelineState;
  warnings: NormalizedWarningState;
  metrics: NormalizedMetricsState;

  // ── Ring buffer of recent task lifecycle events ─────────────────
  events: RuntimeEventEntry[];

  // ── Ring buffer of every recent runtime_event (any subsystem) ───
  recentRuntimeEvents: RecentRuntimeEventEntry[];

  // ── Selection / UI ──────────────────────────────────────────────
  selectedTaskId: string | null;

  // ── Sequencing + observability ──────────────────────────────────
  lastSequence: number;
  stats: ReconciliationStats;

  // ── Actions ─────────────────────────────────────────────────────
  hydrateSnapshot: (snapshot: RuntimeSnapshot, durationMs?: number) => void;
  applyEnvelope: (envelope: RuntimeEnvelope) => void;
  applyReplayBatch: (envelopes: RuntimeEnvelope[]) => void;
  setConnectionPhase: (phase: ConnectionPhase, reconnectAttempts?: number) => void;
  setConnectionState: (state: ConnectionState) => void;
  setRuntimeStatus: (status: RuntimeStatus) => void;
  selectTask: (id: string | null) => void;
  clearEvents: () => void;
  reset: () => void;
}

const INITIAL_CONNECTION: ConnectionMeta = {
  phase: "idle",
  state: "idle",
  reconnectAttempts: 0,
  lastFrameAtMonotonicMs: 0,
};

const INITIAL_RUNTIME: RuntimeMeta = INITIAL_RUNTIME_META;

const INITIAL_REPLAY: ReplayMeta = {
  oldestRetainedSequence: null,
  newestRetainedSequence: null,
  windowHit: true,
};

const INITIAL_QUEUE: QueueMeta = {
  queue: null,
};

const INITIAL_STATS: ReconciliationStats = INITIAL_RECONCILIATION_STATS;

const INITIAL_TIMELINE: NormalizedTimelineState = {
  segmentsById: {},
  activeSegmentsByTaskId: {},
  segmentIdsByTaskId: {},
  lastSequence: 0,
};

const INITIAL_WARNINGS: NormalizedWarningState = {
  warningsById: {},
  activeWarningIds: [],
  resolvedWarningIds: [],
  countsBySeverity: { info: 0, warning: 0, error: 0, critical: 0 },
};

const INITIAL_METRICS: NormalizedMetricsState = {
  aggregate: null,
  deltaCounts: {},
};

const INITIAL_STATE = {
  connection: INITIAL_CONNECTION,
  runtime: INITIAL_RUNTIME,
  replay: INITIAL_REPLAY,
  queue: INITIAL_QUEUE,
  tasksById: {} as Record<string, TaskSnapshot>,
  taskIdsByState: {
    created: [],
    running: [],
    waiting: [],
    completed: [],
    cancelled: [],
    failed: [],
  } as Record<TaskLifecycleState, string[]>,
  timeline: INITIAL_TIMELINE,
  warnings: INITIAL_WARNINGS,
  metrics: INITIAL_METRICS,
  events: [] as RuntimeEventEntry[],
  recentRuntimeEvents: [] as RecentRuntimeEventEntry[],
  selectedTaskId: null as string | null,
  lastSequence: 0,
  stats: INITIAL_STATS,
};

export const useRuntimeStore = create<RuntimeStoreState>((set) => ({
  ...INITIAL_STATE,

  hydrateSnapshot: (snapshot, durationMs = 0) =>
    set((prev) => {
      const stateSnapshot = snapshot.state;
      const { tasksById, taskIdsByState } = normalizeTasks(
        stateSnapshot?.tasks ?? extractTasksFromStateOnly(stateSnapshot),
      );
      const timeline = normalizeTimeline(snapshot);
      const warnings = normalizeWarnings(snapshot);
      const metricsAggregate: RuntimeMetricsAggregateSnapshot | null = snapshot.metrics;
      return {
        connection: {
          ...prev.connection,
          lastFrameAtMonotonicMs: performance.now(),
        },
        runtime: {
          ...prev.runtime,
          runtimeId: snapshot.metadata.runtime_id,
          clock: snapshot.clock,
        },
        replay: {
          oldestRetainedSequence: snapshot.consistency.oldest_retained_sequence,
          newestRetainedSequence: snapshot.consistency.newest_retained_sequence,
          windowHit: snapshot.consistency.replay_window_hit,
        },
        queue: { queue: snapshot.queue },
        tasksById,
        taskIdsByState,
        timeline,
        warnings,
        metrics: {
          aggregate: metricsAggregate,
          deltaCounts: {},
        },
        lastSequence: snapshot.consistency.last_sequence,
        stats: {
          ...prev.stats,
          hydrations: prev.stats.hydrations + 1,
          lastHydrationDurationMs: durationMs,
        },
      };
    }),

  applyEnvelope: (envelope) => set((prev) => applyEnvelopeReducer(prev, envelope)),

  applyReplayBatch: (envelopes) =>
    set((prev) => {
      let current = prev;
      for (const envelope of envelopes) {
        const partial = applyEnvelopeReducer(current, envelope);
        current = { ...current, ...partial };
      }
      return current;
    }),

  setConnectionPhase: (phase, reconnectAttempts) =>
    set((prev) => ({
      connection: {
        ...prev.connection,
        phase,
        state: toConnectionState(phase),
        reconnectAttempts: reconnectAttempts ?? prev.connection.reconnectAttempts,
      },
    })),

  setConnectionState: (state) =>
    set((prev) => ({
      connection: { ...prev.connection, state },
    })),

  setRuntimeStatus: (status) => set((prev) => ({ runtime: { ...prev.runtime, status } })),

  selectTask: (selectedTaskId) => set({ selectedTaskId }),

  clearEvents: () => set({ events: [] }),

  reset: () => set({ ...INITIAL_STATE }),
}));

// ── Reducer dispatch ─────────────────────────────────────────────────

function applyEnvelopeReducer(
  prev: RuntimeStoreState,
  envelope: RuntimeEnvelope,
): Partial<RuntimeStoreState> {
  // Sequence-gated dispatch: duplicates + stale are dropped + counted.
  if (
    envelope.type === "runtime_event" ||
    envelope.type === "metrics_delta" ||
    envelope.type === "warning_delta" ||
    envelope.type === "timeline_delta"
  ) {
    const decision = decideStoreSequence(envelope, prev.lastSequence);
    if (decision === "duplicate") {
      return { stats: { ...prev.stats, duplicatesDropped: prev.stats.duplicatesDropped + 1 } };
    }
    if (decision === "stale") {
      return { stats: { ...prev.stats, staleDropped: prev.stats.staleDropped + 1 } };
    }
  }

  switch (envelope.type) {
    case "heartbeat":
      return reduceHeartbeatEnvelope(prev, envelope);
    case "system_status":
      return reduceSystemStatusEnvelope(prev, envelope);
    case "runtime_snapshot":
      return reduceRuntimeSnapshotEnvelope(prev, envelope);
    case "runtime_event":
      return reduceRuntimeEventEnvelope(prev, envelope);
    case "metrics_delta":
      return reduceMetricsDeltaEnvelope(prev, envelope);
    case "warning_delta":
      return reduceWarningDeltaEnvelope(prev, envelope);
    case "timeline_delta":
      return reduceTimelineDeltaEnvelope(prev, envelope);
    case "protocol_error":
      return { stats: { ...prev.stats, protocolErrors: prev.stats.protocolErrors + 1 } };
    case "replay_status":
      return reduceReplayStatusEnvelope(prev, envelope);
  }
}

const KNOWN_REPLAY_PLAYBACK_STATES = new Set<RuntimeMeta["replayPlaybackState"]>([
  "idle",
  "playing",
  "paused",
  "seeking",
  "buffering",
  "stopped",
  "failed",
]);

function reduceReplayStatusEnvelope(
  prev: RuntimeStoreState,
  envelope: RuntimeEnvelope,
): Partial<RuntimeStoreState> {
  // The per-feature ``WebSocketReplayEngineBridge`` consumes the
  // payload's ``recording`` + ``window`` slots directly. The central
  // store only mirrors the two fields the header projection needs to
  // tell LIVE from REPLAY (and PAUSED / STOPPED inside replay mode).
  // Anything else lives in the replay-page store and stays out of
  // the central reducer's normalization surface.
  const payload = envelope.payload as { playback?: { state?: unknown } } | undefined;
  const rawState = payload?.playback?.state;
  const replayPlaybackState: RuntimeMeta["replayPlaybackState"] = (
    typeof rawState === "string" && KNOWN_REPLAY_PLAYBACK_STATES.has(
      rawState as RuntimeMeta["replayPlaybackState"],
    )
      ? (rawState as RuntimeMeta["replayPlaybackState"])
      : prev.runtime.replayPlaybackState
  );
  return {
    runtime: {
      ...prev.runtime,
      // Once any ``replay_status`` envelope arrives this connection
      // is a replay session for its lifetime. Don't flip back to
      // false on a malformed payload — the broadcaster sends one
      // every ~0.5 s, so even transient corruption is recoverable.
      replayActive: true,
      replayPlaybackState,
    },
    connection: { ...prev.connection, lastFrameAtMonotonicMs: performance.now() },
    stats: { ...prev.stats, envelopesApplied: prev.stats.envelopesApplied + 1 },
  };
}

function reduceHeartbeatEnvelope(
  prev: RuntimeStoreState,
  envelope: RuntimeEnvelope,
): Partial<RuntimeStoreState> {
  const projection = reduceHeartbeat(
    {
      serverUptimeSeconds: prev.runtime.serverUptimeSeconds,
      connectedClients: prev.runtime.connectedClients,
    },
    envelope.payload as Partial<HeartbeatPayload>,
  );
  return {
    connection: { ...prev.connection, lastFrameAtMonotonicMs: performance.now() },
    runtime: {
      ...prev.runtime,
      serverUptimeSeconds: projection.serverUptimeSeconds,
      connectedClients: projection.connectedClients,
    },
    stats: { ...prev.stats, envelopesApplied: prev.stats.envelopesApplied + 1 },
  };
}

function reduceSystemStatusEnvelope(
  prev: RuntimeStoreState,
  envelope: RuntimeEnvelope,
): Partial<RuntimeStoreState> {
  const payload = envelope.payload as { runtime_status?: string };
  const status = isRuntimeStatus(payload.runtime_status)
    ? (payload.runtime_status as RuntimeStatus)
    : prev.runtime.status;
  return {
    runtime: { ...prev.runtime, status },
    connection: { ...prev.connection, lastFrameAtMonotonicMs: performance.now() },
    stats: { ...prev.stats, envelopesApplied: prev.stats.envelopesApplied + 1 },
  };
}

const KNOWN_RUNTIME_STATUSES = new Set(["idle", "running", "paused", "stopped", "shutting_down"]);

function isRuntimeStatus(value: unknown): boolean {
  return typeof value === "string" && KNOWN_RUNTIME_STATUSES.has(value);
}

function reduceRuntimeSnapshotEnvelope(
  prev: RuntimeStoreState,
  envelope: RuntimeEnvelope,
): Partial<RuntimeStoreState> {
  // Legacy envelope shape — `payload.tasks` + `payload.last_sequence`
  // + `payload.clock` + `payload.queue` + `payload.state`. The current
  // backend nests a full `state` in the payload.
  const payload = envelope.payload as {
    tasks?: TaskSnapshot[];
    last_sequence?: number;
    clock?: ClockSnapshot | null;
    queue?: QueueSnapshot | null;
    state?: RuntimeStateSnapshot | null;
  };
  const tasks = Array.isArray(payload.tasks) ? payload.tasks : (payload.state?.tasks ?? []);
  const { tasksById, taskIdsByState } = normalizeTasks(tasks);
  const last = typeof payload.last_sequence === "number" ? payload.last_sequence : 0;
  return {
    tasksById,
    taskIdsByState,
    lastSequence: maxSequence(prev.lastSequence, last),
    runtime: {
      ...prev.runtime,
      clock: payload.clock ?? prev.runtime.clock,
    },
    queue: { queue: payload.queue ?? prev.queue.queue },
    connection: { ...prev.connection, lastFrameAtMonotonicMs: performance.now() },
    stats: { ...prev.stats, envelopesApplied: prev.stats.envelopesApplied + 1 },
  };
}

function reduceRuntimeEventEnvelope(
  prev: RuntimeStoreState,
  envelope: RuntimeEnvelope,
): Partial<RuntimeStoreState> {
  // Every runtime_event — task lifecycle, queue, gather, semaphore,
  // executor, runtime.*, blocked, etc. — must always:
  //
  //   * advance the store's sequence cursor
  //   * tick stats.envelopesApplied
  //   * refresh connection.lastFrameAtMonotonicMs so the heartbeat
  //     freshness signal stays honest while live traffic flows
  //   * land in the recentRuntimeEvents observability ring
  //
  // ONLY events recognized as task lifecycle (``asyncio.task.*``)
  // mutate the task projections (``tasksById`` / ``taskIdsByState`` /
  // ``events`` task-lifecycle ring). Per-subsystem state for queues,
  // executors, etc. is owned by dedicated websocket bridges that
  // subscribe directly to the websocket client — we deliberately do
  // not duplicate that normalization here.
  const trace = describeRuntimeEvent(envelope);
  const categoryUpdate =
    trace.category === ""
      ? prev.stats.runtimeEventsByCategory
      : {
          ...prev.stats.runtimeEventsByCategory,
          [trace.category]: (prev.stats.runtimeEventsByCategory[trace.category] ?? 0) + 1,
        };
  const recentRuntimeEvents = appendBounded(
    prev.recentRuntimeEvents,
    trace,
    RECENT_RUNTIME_EVENT_LIMIT,
  );
  const baseStats: ReconciliationStats = {
    ...prev.stats,
    envelopesApplied: prev.stats.envelopesApplied + 1,
    runtimeEventsByCategory: categoryUpdate,
    unhandledRuntimeEvents:
      trace.eventType === "unknown"
        ? prev.stats.unhandledRuntimeEvents + 1
        : prev.stats.unhandledRuntimeEvents,
  };
  const baseUpdate: Partial<RuntimeStoreState> = {
    recentRuntimeEvents,
    lastSequence: maxSequence(prev.lastSequence, envelope.sequence),
    connection: { ...prev.connection, lastFrameAtMonotonicMs: performance.now() },
    stats: baseStats,
  };

  if (!isTaskLifecycleEvent(envelope.payload)) {
    return baseUpdate;
  }

  // Task lifecycle path — additionally update task projections.
  const event = envelope.payload as TaskLifecycleEvent;
  const existing = prev.tasksById[event.task_id];
  const { next, regressed } = reduceTaskEvent(event, existing);
  const tasksById = { ...prev.tasksById, [event.task_id]: next };
  const taskIdsByState = reindexTaskState(
    prev.taskIdsByState,
    event.task_id,
    existing?.state,
    next.state,
  );
  const events = appendBounded(prev.events, event, EVENT_BUFFER_LIMIT);
  return {
    ...baseUpdate,
    tasksById,
    taskIdsByState,
    events,
    stats: {
      ...baseStats,
      regressionsSuppressed: regressed
        ? baseStats.regressionsSuppressed + 1
        : baseStats.regressionsSuppressed,
    },
  };
}

/**
 * Drop the oldest entries when ``items`` would exceed ``limit``.
 *
 * Returns a new array; never mutates the input. ``limit`` is treated
 * as an inclusive max — the result always has ``length <= limit``.
 */
function appendBounded<T>(items: readonly T[], entry: T, limit: number): T[] {
  if (limit <= 0) return [];
  if (items.length < limit) return [...items, entry];
  return [...items.slice(items.length - limit + 1), entry];
}

/**
 * Extract the trace-line projection for the recent-events ring buffer.
 *
 * Falls back to ``"unknown"`` event type + empty category when the
 * payload is missing the ``event_type`` discriminator. The caller
 * counts those separately via ``stats.unhandledRuntimeEvents`` so a
 * wire-protocol regression has a visible diagnostics surface.
 */
function describeRuntimeEvent(envelope: RuntimeEnvelope): RecentRuntimeEventEntry {
  const rawPayload = envelope.payload as Record<string, unknown> | null | undefined;
  const payload: Record<string, unknown> = rawPayload ?? {};
  const rawEventType = (payload as { event_type?: unknown }).event_type;
  const eventType = typeof rawEventType === "string" && rawEventType !== "" ? rawEventType : "unknown";
  const rawTaskId = (payload as { task_id?: unknown }).task_id;
  const taskId = typeof rawTaskId === "string" ? rawTaskId : null;
  return {
    sequence: typeof envelope.sequence === "number" ? envelope.sequence : null,
    eventType,
    category: categorizeEventType(eventType),
    timestamp: envelope.timestamp,
    taskId,
    payload,
  };
}

/**
 * Reduce ``event_type`` to its histogram bucket.
 *
 *   ``"asyncio.task.created"`` → ``"asyncio.task"``
 *   ``"asyncio.queue.put"``    → ``"asyncio.queue"``
 *   ``"runtime.metric"``       → ``"runtime.metric"`` (already at the prefix)
 *   ``"unknown"``              → ``""`` (don't pollute the histogram)
 *
 * Two-component grouping is what the Diagnostics page consumes —
 * granular enough to show queues vs. semaphores separately, coarse
 * enough that the histogram doesn't fragment into one entry per
 * specific event_type.
 */
function categorizeEventType(eventType: string): string {
  if (eventType === "unknown" || eventType === "") return "";
  const parts = eventType.split(".");
  if (parts.length < 2) return eventType;
  return `${parts[0]}.${parts[1]}`;
}

function reduceMetricsDeltaEnvelope(
  prev: RuntimeStoreState,
  envelope: RuntimeEnvelope,
): Partial<RuntimeStoreState> {
  const payload = envelope.payload as unknown as MetricsDeltaPayload;
  const nextMetrics = reduceMetricsDelta(prev.metrics, payload);
  return {
    metrics: nextMetrics,
    lastSequence: maxSequence(prev.lastSequence, envelope.sequence),
    stats: {
      ...prev.stats,
      envelopesApplied: prev.stats.envelopesApplied + 1,
      metricsDeltasApplied: prev.stats.metricsDeltasApplied + 1,
    },
    connection: { ...prev.connection, lastFrameAtMonotonicMs: performance.now() },
  };
}

function reduceWarningDeltaEnvelope(
  prev: RuntimeStoreState,
  envelope: RuntimeEnvelope,
): Partial<RuntimeStoreState> {
  const payload = envelope.payload as unknown as WarningDeltaPayload;
  const nextWarnings = reduceWarningDelta(prev.warnings, payload);
  return {
    warnings: nextWarnings,
    lastSequence: maxSequence(prev.lastSequence, envelope.sequence),
    stats: {
      ...prev.stats,
      envelopesApplied: prev.stats.envelopesApplied + 1,
      warningDeltasApplied: prev.stats.warningDeltasApplied + 1,
    },
    connection: { ...prev.connection, lastFrameAtMonotonicMs: performance.now() },
  };
}

function reduceTimelineDeltaEnvelope(
  prev: RuntimeStoreState,
  envelope: RuntimeEnvelope,
): Partial<RuntimeStoreState> {
  const payload = envelope.payload as unknown as TimelineDeltaPayload;
  const nextTimeline = reduceTimelineDelta(prev.timeline, payload);
  return {
    timeline: nextTimeline,
    lastSequence: maxSequence(prev.lastSequence, envelope.sequence),
    stats: {
      ...prev.stats,
      envelopesApplied: prev.stats.envelopesApplied + 1,
      timelineDeltasApplied: prev.stats.timelineDeltasApplied + 1,
    },
    connection: { ...prev.connection, lastFrameAtMonotonicMs: performance.now() },
  };
}

/** Pull a tasks list from a RuntimeStateSnapshot if the legacy payload's
 *  ``tasks`` field is absent. Returns ``undefined`` when there's nothing
 *  to feed :func:`normalizeTasks`. */
function extractTasksFromStateOnly(
  state: RuntimeStateSnapshot | null | undefined,
): TaskSnapshot[] | undefined {
  if (!state) return undefined;
  return state.tasks;
}
