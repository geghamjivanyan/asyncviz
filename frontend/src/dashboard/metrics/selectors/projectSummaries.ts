/**
 * Pure projections: store state → :type:`MetricsHeaderSnapshot`.
 *
 * Functions here are pure: same inputs → same outputs, no React, no
 * Zustand. They're tested in isolation against synthetic inputs.
 * Hooks higher up the stack memoize the result so React reconciles
 * cheaply.
 */

import type {
  ActiveWarning,
  ClockSnapshot,
  ConnectionState,
  RuntimeStatus,
  TaskLifecycleState,
  TaskSnapshot,
  WarningSeverity,
} from "@/types/runtime";
import type { ConnectionPhase } from "@/runtime/websocket";
import { isConnectingPhase, isLivePhase, isTerminalPhase } from "@/runtime/websocket";
import type {
  ConnectionMeta,
  NormalizedMetricsState,
  NormalizedTimelineState,
  NormalizedWarningState,
  ReconciliationStats,
  ReplayMeta,
  RuntimeMeta,
} from "@/state/runtime";
import {
  emptySeverityCounts,
  highestSeverity,
  totalWarningCount,
  type ConnectionSummary,
  type EventRateSummary,
  type MetricsHeaderSnapshot,
  type ReplaySummary,
  type RuntimeClockSummary,
  type RuntimeHealthSummary,
  type TaskCountSummary,
  type ThroughputSummary,
  type WarningSummary,
} from "@/dashboard/metrics/models/summary";

export interface ProjectionInputs {
  connection: ConnectionMeta;
  runtime: RuntimeMeta;
  replay: ReplayMeta;
  timeline: NormalizedTimelineState;
  warnings: NormalizedWarningState;
  metrics: NormalizedMetricsState;
  stats: ReconciliationStats;
  tasksById: Record<string, TaskSnapshot>;
  taskIdsByState: Record<TaskLifecycleState, string[]>;
  lastSequence: number;
  /** Now-ms used for "last frame ago" rendering. Pure: callers inject. */
  nowMs: number;
  /** Rolling envelope-per-second rate. */
  envelopesPerSecond: number;
}

const CONNECTION_LABEL: Record<ConnectionPhase, string> = {
  idle: "Disconnected",
  hydrating: "Hydrating",
  connecting: "Connecting",
  replaying: "Replaying",
  live: "Live",
  reconnecting: "Reconnecting",
  disconnected: "Disconnected",
  failed: "Failed",
};

const CONNECTION_STATE_LABEL: Record<ConnectionState, string> = {
  idle: "Disconnected",
  connecting: "Connecting",
  open: "Live",
  closed: "Disconnected",
  error: "Failed",
};

const HEALTH_LABEL: Record<RuntimeHealthSummary["level"], string> = {
  healthy: "Healthy",
  degraded: "Degraded",
  unavailable: "Unavailable",
  starting: "Starting",
  unknown: "Unknown",
};

export function projectConnection(inputs: ProjectionInputs): ConnectionSummary {
  const phase = inputs.connection.phase;
  const lastFrame = inputs.connection.lastFrameAtMonotonicMs;
  const lastFrameAgoMs = lastFrame > 0 ? Math.max(0, inputs.nowMs - lastFrame) : null;
  // Fall back to the legacy state label when the phase isn't known
  // (defensive — every value is enumerated above).
  const label = CONNECTION_LABEL[phase] ?? CONNECTION_STATE_LABEL[inputs.connection.state] ?? phase;
  return {
    phase,
    label,
    isLive: isLivePhase(phase),
    isReconnecting: phase === "reconnecting",
    hasError: isTerminalPhase(phase) && phase === "failed",
    reconnectAttempts: inputs.connection.reconnectAttempts,
    connectedClients: inputs.runtime.connectedClients,
    lastFrameAgoMs,
  };
}

export function projectReplay(inputs: ProjectionInputs): ReplaySummary {
  const newest = inputs.replay.newestRetainedSequence;
  const oldest = inputs.replay.oldestRetainedSequence;
  let cursorProgress = 0;
  if (newest !== null && newest > 0) {
    cursorProgress = Math.min(1, Math.max(0, inputs.lastSequence / newest));
  } else if (inputs.lastSequence > 0) {
    cursorProgress = 1;
  }
  return {
    windowHit: inputs.replay.windowHit,
    oldestRetainedSequence: oldest,
    newestRetainedSequence: newest,
    lastSequence: inputs.lastSequence,
    hydrations: inputs.stats.hydrations,
    cursorProgress,
    isReplaying: inputs.connection.phase === "replaying",
  };
}

export function projectWarnings(inputs: ProjectionInputs): WarningSummary {
  const counts = { ...emptySeverityCounts(), ...inputs.warnings.countsBySeverity };
  return {
    countsBySeverity: counts,
    total: totalWarningCount(counts),
    highest: highestSeverity(counts),
    resolved: inputs.warnings.resolvedWarningIds.length,
  };
}

export function projectTaskCounts(inputs: ProjectionInputs): TaskCountSummary {
  const buckets = inputs.taskIdsByState;
  const active = buckets.running.length;
  const waiting = buckets.waiting.length;
  const completed = buckets.completed.length;
  const cancelled = buckets.cancelled.length;
  const failed = buckets.failed.length;
  const created = buckets.created.length;
  const terminal = completed + cancelled + failed;
  return {
    total: active + waiting + completed + cancelled + failed + created,
    active,
    waiting,
    completed,
    cancelled,
    failed,
    terminal,
  };
}

export function projectThroughput(inputs: ProjectionInputs): ThroughputSummary {
  const aggregate = inputs.metrics.aggregate;
  const throughput = aggregate?.throughput;
  if (throughput === undefined) {
    return {
      tasksPerSecond: 0,
      completionsPerSecond: 0,
      failuresPerSecond: 0,
      cancellationsPerSecond: 0,
      windowSeconds: 0,
    };
  }
  return {
    tasksPerSecond: safeNumber(throughput.tasks_per_second),
    completionsPerSecond: safeNumber(throughput.completions_per_second),
    failuresPerSecond: safeNumber(throughput.failures_per_second),
    cancellationsPerSecond: safeNumber(throughput.cancellations_per_second),
    windowSeconds: safeNumber(throughput.window_seconds),
  };
}

export function projectEventRate(inputs: ProjectionInputs): EventRateSummary {
  return {
    envelopesApplied: inputs.stats.envelopesApplied,
    staleDropped: inputs.stats.staleDropped,
    duplicatesDropped: inputs.stats.duplicatesDropped,
    protocolErrors: inputs.stats.protocolErrors,
    envelopesPerSecond: Math.max(0, inputs.envelopesPerSecond),
  };
}

export function projectClock(inputs: ProjectionInputs): RuntimeClockSummary {
  const clock: ClockSnapshot | null = inputs.runtime.clock;
  return {
    uptimeSeconds: clock?.uptime_seconds ?? 0,
    wallNowMs: clock !== null ? clock.wall_now_seconds * 1000 : null,
    serverUptimeSeconds: inputs.runtime.serverUptimeSeconds,
  };
}

export function projectHealth(
  inputs: ProjectionInputs,
  warnings: WarningSummary,
  connection: ConnectionSummary,
  replay: ReplaySummary,
): RuntimeHealthSummary {
  const status: RuntimeStatus = inputs.runtime.status;
  const hasCritical = warnings.countsBySeverity.critical > 0;
  const hasError = warnings.countsBySeverity.error > 0;
  const isPaused = status === "paused" || status === "stopped";
  const isHydrating = isConnectingPhase(connection.phase);
  let level: RuntimeHealthSummary["level"] = "unknown";

  if (connection.hasError || !replay.windowHit) {
    level = "unavailable";
  } else if (hasCritical) {
    level = "unavailable";
  } else if (hasError || isPaused) {
    level = "degraded";
  } else if (connection.isLive) {
    level = "healthy";
  } else if (isHydrating) {
    level = "starting";
  } else {
    level = "unknown";
  }

  return {
    level,
    label: HEALTH_LABEL[level],
    isHydrating,
    hasCriticalWarning: hasCritical,
    isPaused,
  };
}

/** Top-level projection — composes every sub-projection. */
export function projectMetricsHeader(inputs: ProjectionInputs): MetricsHeaderSnapshot {
  const connection = projectConnection(inputs);
  const replay = projectReplay(inputs);
  const warnings = projectWarnings(inputs);
  const taskCounts = projectTaskCounts(inputs);
  const throughput = projectThroughput(inputs);
  const eventRate = projectEventRate(inputs);
  const clock = projectClock(inputs);
  const health = projectHealth(inputs, warnings, connection, replay);
  const signature = computeSignature({
    health,
    connection,
    replay,
    warnings,
    throughput,
    eventRate,
    taskCounts,
    clock,
  });
  return {
    health,
    connection,
    replay,
    warnings,
    throughput,
    eventRate,
    taskCounts,
    clock,
    signature,
  };
}

function safeNumber(value: number | null | undefined): number {
  if (value == null || !Number.isFinite(value)) return 0;
  return value;
}

function computeSignature(snapshot: Omit<MetricsHeaderSnapshot, "signature">): string {
  return [
    snapshot.health.level,
    snapshot.health.isPaused ? 1 : 0,
    snapshot.connection.phase,
    snapshot.connection.reconnectAttempts,
    snapshot.connection.connectedClients,
    snapshot.replay.windowHit ? 1 : 0,
    snapshot.replay.lastSequence,
    snapshot.replay.newestRetainedSequence ?? "",
    snapshot.warnings.total,
    snapshot.warnings.highest ?? "",
    snapshot.taskCounts.total,
    snapshot.taskCounts.active,
    snapshot.taskCounts.failed,
    snapshot.throughput.tasksPerSecond.toFixed(3),
    snapshot.eventRate.envelopesApplied,
    snapshot.eventRate.envelopesPerSecond.toFixed(3),
    Math.round(snapshot.clock.uptimeSeconds),
  ].join("|");
}

/** Hard-coded re-exports for the convenience of consumers. */
export type { WarningSeverity, ActiveWarning };
