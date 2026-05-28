/**
 * Canonical summary models for the metrics header.
 *
 * The store keeps every metric as a raw projection (counts, deltas,
 * warning index). The metrics header works on narrower projections —
 * one per card. Projections live here so selectors and components
 * stay UI-shaped, and downstream consumers (sparklines, sorting,
 * accessibility) operate on stable shapes.
 *
 * Every summary is *immutable* and *referentially stable*: a memoized
 * selector returns the same object reference as long as the inputs
 * are unchanged.
 */

import type { WarningSeverity } from "@/types/runtime";
import type { ConnectionPhase } from "@/runtime/websocket";

/**
 * High-level runtime health state. Mapping is intentionally coarser
 * than the backend ``HealthStatus`` enum — the header only needs a
 * three-state signal (healthy / degraded / unavailable), with two
 * extra "in-between" states for live UX.
 */
export type RuntimeHealthLevel = "healthy" | "degraded" | "unavailable" | "starting" | "unknown";

export interface RuntimeHealthSummary {
  level: RuntimeHealthLevel;
  /** Human-readable label rendered in the badge. */
  label: string;
  /** ``true`` while the runtime is hydrating from the snapshot. */
  isHydrating: boolean;
  /** ``true`` when at least one critical warning is active. */
  hasCriticalWarning: boolean;
  /** ``true`` when the runtime is paused/stopped. */
  isPaused: boolean;
}

export interface ReplaySummary {
  /** ``true`` when the snapshot satisfied the requested cursor. */
  windowHit: boolean;
  /** Lowest sequence the backend can satisfy. */
  oldestRetainedSequence: number | null;
  /** Highest sequence the backend can satisfy. */
  newestRetainedSequence: number | null;
  /** Current store sequence — the live cursor. */
  lastSequence: number;
  /** Number of envelopes the store has hydrated through. */
  hydrations: number;
  /** Replay throughput indicator — ratio of last_sequence / newest. */
  cursorProgress: number;
  /** ``true`` when we're explicitly inside a replay window. */
  isReplaying: boolean;
}

export interface ConnectionSummary {
  phase: ConnectionPhase;
  label: string;
  /** ``true`` when the websocket is connected + live. */
  isLive: boolean;
  /** ``true`` when the client is attempting reconnect. */
  isReconnecting: boolean;
  /** ``true`` when the client is in an error/failed state. */
  hasError: boolean;
  /** Reconnect attempts since the last clean start. */
  reconnectAttempts: number;
  /** Connected client count from the most recent heartbeat. */
  connectedClients: number;
  /** Milliseconds since the last frame was applied. */
  lastFrameAgoMs: number | null;
}

export interface WarningSummary {
  /** Active warning count, broken out by severity. */
  countsBySeverity: Record<WarningSeverity, number>;
  /** Sum across every severity. */
  total: number;
  /** Highest active severity — null when there are no warnings. */
  highest: WarningSeverity | null;
  /** Number of resolved warnings observed in the current session. */
  resolved: number;
}

export interface ThroughputSummary {
  /** Tasks-per-second from the latest aggregate. */
  tasksPerSecond: number;
  /** Completions-per-second. */
  completionsPerSecond: number;
  /** Failures-per-second. */
  failuresPerSecond: number;
  /** Cancellations-per-second. */
  cancellationsPerSecond: number;
  /** Window size in seconds that the rates were computed over. */
  windowSeconds: number;
}

export interface EventRateSummary {
  /** Envelopes folded into the store since the last hydration. */
  envelopesApplied: number;
  /** Stale-sequence drops (signal for replay disagreement). */
  staleDropped: number;
  /** Duplicate-sequence drops. */
  duplicatesDropped: number;
  /** Protocol-error frames. */
  protocolErrors: number;
  /** Computed rate per second (rolling, over a fixed window). */
  envelopesPerSecond: number;
}

export interface TaskCountSummary {
  total: number;
  active: number;
  waiting: number;
  completed: number;
  cancelled: number;
  failed: number;
  terminal: number;
}

export interface RuntimeClockSummary {
  /** Wall seconds the runtime has been alive. */
  uptimeSeconds: number;
  /** Last reported wall time, ms since epoch. */
  wallNowMs: number | null;
  /** Heartbeat-reported server uptime. */
  serverUptimeSeconds: number;
}

/** Composite shape passed to the header — a snapshot of every card. */
export interface MetricsHeaderSnapshot {
  health: RuntimeHealthSummary;
  connection: ConnectionSummary;
  replay: ReplaySummary;
  warnings: WarningSummary;
  throughput: ThroughputSummary;
  eventRate: EventRateSummary;
  taskCounts: TaskCountSummary;
  clock: RuntimeClockSummary;
  /** Content signature — folds every visible field for memo + tests. */
  signature: string;
}

const EMPTY_SEVERITY_COUNTS: Record<WarningSeverity, number> = {
  info: 0,
  warning: 0,
  error: 0,
  critical: 0,
};

export function emptySeverityCounts(): Record<WarningSeverity, number> {
  return { ...EMPTY_SEVERITY_COUNTS };
}

/** Severity-ordering helper — higher is more severe. */
export const WARNING_SEVERITY_RANK: Record<WarningSeverity, number> = {
  info: 1,
  warning: 2,
  error: 3,
  critical: 4,
};

/** Pure: pick the highest severity present in a counts map. */
export function highestSeverity(counts: Record<WarningSeverity, number>): WarningSeverity | null {
  const severities: WarningSeverity[] = ["critical", "error", "warning", "info"];
  for (const sev of severities) {
    if ((counts[sev] ?? 0) > 0) return sev;
  }
  return null;
}

/** Pure: total across every severity. */
export function totalWarningCount(counts: Record<WarningSeverity, number>): number {
  return (counts.info ?? 0) + (counts.warning ?? 0) + (counts.error ?? 0) + (counts.critical ?? 0);
}
