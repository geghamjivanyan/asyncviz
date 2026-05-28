/**
 * Pure reducers for the runtime store.
 *
 * Each function takes the relevant slice of state + a delta/envelope
 * and returns the *next* slice. Reducers never read or write the
 * store directly — the Zustand store wires them into ``set()`` calls
 * in ``store.ts``.
 *
 * Keeping reducers pure means we can:
 *   * Unit-test them deterministically.
 *   * Replay a batch of envelopes against an initial state to verify
 *     hydration equivalence.
 *   * Move them off the main thread later if needed.
 */

import type {
  ActiveWarning,
  HeartbeatPayload,
  MetricsDeltaPayload,
  RuntimeEnvelope,
  TaskLifecycleEvent,
  TaskLifecycleState,
  TaskSnapshot,
  TimelineDeltaPayload,
  WarningDeltaPayload,
} from "@/types/runtime";
import {
  TASK_STATES,
  TERMINAL_TASK_STATES,
  type NormalizedMetricsState,
  type NormalizedTimelineState,
  type NormalizedWarningState,
} from "@/state/runtime/models";

const TASK_EVENT_TYPES = new Set([
  "asyncio.task.created",
  "asyncio.task.started",
  "asyncio.task.waiting",
  "asyncio.task.resumed",
  "asyncio.task.completed",
  "asyncio.task.cancelled",
  "asyncio.task.failed",
]);

const EVENT_TO_STATE: Record<string, TaskLifecycleState | undefined> = {
  "asyncio.task.created": "created",
  "asyncio.task.started": "running",
  "asyncio.task.waiting": "waiting",
  "asyncio.task.resumed": "running",
  "asyncio.task.completed": "completed",
  "asyncio.task.cancelled": "cancelled",
  "asyncio.task.failed": "failed",
};

export function isTaskLifecycleEvent(value: unknown): value is TaskLifecycleEvent {
  if (typeof value !== "object" || value === null) return false;
  const eventType = (value as { event_type?: unknown }).event_type;
  return typeof eventType === "string" && TASK_EVENT_TYPES.has(eventType);
}

// ── Task lifecycle reducer ────────────────────────────────────────────

export interface TaskReduceResult {
  next: TaskSnapshot;
  regressed: boolean;
}

/**
 * Fold one :type:`TaskLifecycleEvent` into the matching task record.
 *
 * Regression guard: once a task is in a terminal state, it's frozen.
 * Non-terminal events that arrive late are merged for metadata (name,
 * coroutine_name) but never flip ``state`` back to a non-terminal
 * value. ``regressed`` reports whether the guard fired.
 */
export function reduceTaskEvent(
  event: TaskLifecycleEvent,
  existing: TaskSnapshot | undefined,
): TaskReduceResult {
  const incomingState = EVENT_TO_STATE[event.event_type] ?? "created";

  const existingTerminal = existing != null && TERMINAL_TASK_STATES.has(existing.state);
  const incomingTerminal = TERMINAL_TASK_STATES.has(incomingState);
  const wouldRegress = existingTerminal && !incomingTerminal;
  const effectiveState: TaskLifecycleState = wouldRegress ? existing!.state : incomingState;

  const now = event.timestamp;
  const base: TaskSnapshot = existing ?? {
    task_id: event.task_id,
    state: effectiveState,
    created_at: now,
    updated_at: now,
    asyncio_task_id: null,
    coroutine_name: event.coroutine_name,
    task_name: event.task_name,
    parent_task_id: event.parent_task_id,
    root_task_id: event.task_id,
    depth: 0,
    ancestor_chain: [],
    child_count: 0,
    completed_at: null,
    duration_seconds: null,
    exception_type: null,
    exception_message: null,
    cancellation_origin: null,
    runtime_id: event.runtime_id,
    tags: {},
    metadata: { ...event.metadata },
  };

  const next: TaskSnapshot = {
    ...base,
    state: effectiveState,
    updated_at: now,
    coroutine_name: event.coroutine_name ?? base.coroutine_name,
    task_name: event.task_name ?? base.task_name,
    parent_task_id: event.parent_task_id ?? base.parent_task_id,
  };

  if ("duration_seconds" in event && event.duration_seconds != null) {
    next.duration_seconds = event.duration_seconds;
  }
  if ("created_at" in event && event.created_at != null) {
    next.created_at = event.created_at;
  }
  if ("completed_at" in event && event.completed_at != null) {
    next.completed_at = event.completed_at;
  } else if (incomingTerminal) {
    next.completed_at = now;
  }
  if (event.event_type === "asyncio.task.failed") {
    next.exception_type = event.exception_type;
    next.exception_message = event.exception_message;
  }
  if (event.event_type === "asyncio.task.cancelled" && event.cancellation_origin != null) {
    next.cancellation_origin = event.cancellation_origin;
  }
  return { next, regressed: wouldRegress };
}

/**
 * Replace ``taskIdsByState`` for one task that moved states.
 *
 * Pure: returns a new index. Callers always re-bucket the task even
 * when the state didn't change — it's cheap and keeps the buckets
 * authoritative.
 */
export function reindexTaskState(
  taskIdsByState: Record<TaskLifecycleState, string[]>,
  taskId: string,
  fromState: TaskLifecycleState | undefined,
  toState: TaskLifecycleState,
): Record<TaskLifecycleState, string[]> {
  const next: Record<TaskLifecycleState, string[]> = { ...taskIdsByState };
  if (fromState !== undefined && fromState !== toState) {
    const sourceBucket = next[fromState];
    if (sourceBucket !== undefined) {
      const idx = sourceBucket.indexOf(taskId);
      if (idx >= 0) {
        next[fromState] = [...sourceBucket.slice(0, idx), ...sourceBucket.slice(idx + 1)];
      }
    }
  }
  const destBucket = next[toState];
  if (destBucket === undefined) {
    next[toState] = [taskId];
  } else if (!destBucket.includes(taskId)) {
    next[toState] = [...destBucket, taskId];
  }
  return next;
}

// ── Heartbeat reducer ─────────────────────────────────────────────────

export interface HeartbeatProjection {
  serverUptimeSeconds: number;
  connectedClients: number;
}

export function reduceHeartbeat(
  prev: HeartbeatProjection,
  payload: Partial<HeartbeatPayload>,
): HeartbeatProjection {
  return {
    serverUptimeSeconds:
      typeof payload.server_uptime_seconds === "number"
        ? payload.server_uptime_seconds
        : prev.serverUptimeSeconds,
    connectedClients:
      typeof payload.connected_clients === "number"
        ? payload.connected_clients
        : prev.connectedClients,
  };
}

// ── Metrics delta reducer ─────────────────────────────────────────────

export function reduceMetricsDelta(
  prev: NormalizedMetricsState,
  payload: MetricsDeltaPayload,
): NormalizedMetricsState {
  const merged: Record<string, number> = { ...prev.deltaCounts };
  for (const [key, value] of Object.entries(payload.changes ?? {})) {
    if (typeof value !== "number" || !Number.isFinite(value)) continue;
    merged[key] = (merged[key] ?? 0) + value;
  }
  return { aggregate: prev.aggregate, deltaCounts: merged };
}

// ── Warning delta reducer ─────────────────────────────────────────────

const VALID_CHANGES = new Set(["activated", "updated", "deduplicated", "resolved", "expired"]);

export function reduceWarningDelta(
  prev: NormalizedWarningState,
  payload: WarningDeltaPayload,
): NormalizedWarningState {
  if (payload.warning === undefined || !VALID_CHANGES.has(payload.change)) {
    return prev;
  }
  const warning: ActiveWarning = payload.warning;
  const id = warning.warning_id;

  const warningsById: Record<string, ActiveWarning> = { ...prev.warningsById, [id]: warning };
  let activeWarningIds = prev.activeWarningIds;
  let resolvedWarningIds = prev.resolvedWarningIds;
  const countsBySeverity = { ...prev.countsBySeverity };

  const isResolved = payload.change === "resolved" || payload.change === "expired";
  const previouslyActive = prev.activeWarningIds.includes(id);

  if (isResolved) {
    if (previouslyActive) {
      activeWarningIds = activeWarningIds.filter((wid) => wid !== id);
    }
    if (!resolvedWarningIds.includes(id)) {
      resolvedWarningIds = [...resolvedWarningIds, id];
    }
    // Decrement severity counter for the resolved warning.
    const sev = warning.severity as keyof typeof countsBySeverity;
    if (sev in countsBySeverity && countsBySeverity[sev] > 0) {
      countsBySeverity[sev] = countsBySeverity[sev] - 1;
    }
  } else {
    if (!previouslyActive) {
      activeWarningIds = [...activeWarningIds, id];
      const sev = warning.severity as keyof typeof countsBySeverity;
      if (sev in countsBySeverity) {
        countsBySeverity[sev] = countsBySeverity[sev] + 1;
      }
    }
  }

  return {
    warningsById,
    activeWarningIds,
    resolvedWarningIds,
    countsBySeverity,
  };
}

// ── Timeline delta reducer ────────────────────────────────────────────

export function reduceTimelineDelta(
  prev: NormalizedTimelineState,
  payload: TimelineDeltaPayload,
): NormalizedTimelineState {
  let segmentsById = prev.segmentsById;
  let segmentIdsByTaskId = prev.segmentIdsByTaskId;
  let activeSegmentsByTaskId = prev.activeSegmentsByTaskId;
  const lastSequence =
    typeof payload.sequence === "number" && payload.sequence > prev.lastSequence
      ? payload.sequence
      : prev.lastSequence;

  if (payload.kind === "segment_closed" && payload.segment !== undefined) {
    const seg = payload.segment;
    segmentsById = { ...segmentsById, [seg.segment_id]: seg };
    const bucket = segmentIdsByTaskId[seg.task_id] ?? [];
    if (!bucket.includes(seg.segment_id)) {
      segmentIdsByTaskId = {
        ...segmentIdsByTaskId,
        [seg.task_id]: [...bucket, seg.segment_id],
      };
    }
    // Closing a segment removes the open one for that task.
    if (activeSegmentsByTaskId[seg.task_id] !== undefined) {
      const next = { ...activeSegmentsByTaskId };
      delete next[seg.task_id];
      activeSegmentsByTaskId = next;
    }
  }

  if (payload.kind === "segment_opened" && payload.open_segment !== undefined) {
    activeSegmentsByTaskId = {
      ...activeSegmentsByTaskId,
      [payload.task_id]: payload.open_segment,
    };
  }

  if (payload.kind === "span_finalized") {
    if (activeSegmentsByTaskId[payload.task_id] !== undefined) {
      const next = { ...activeSegmentsByTaskId };
      delete next[payload.task_id];
      activeSegmentsByTaskId = next;
    }
  }

  return {
    segmentsById,
    segmentIdsByTaskId,
    activeSegmentsByTaskId,
    lastSequence,
  };
}

// ── Envelope dispatch ─────────────────────────────────────────────────

/** Best-effort discriminator for envelope payloads — replaces a giant
 *  switch with a typed helper that callers compose with ``reduce*``. */
export function classifyEnvelope(env: RuntimeEnvelope): string {
  return env.type;
}

/** Re-export for callers that build task lists from snapshots. */
export { TASK_STATES };
