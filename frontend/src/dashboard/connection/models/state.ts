/**
 * Canonical state shapes for the connection-status system.
 *
 * The runtime store keeps the raw lifecycle data — phase, reconnect
 * attempts, last frame timestamp, replay window. The indicator works
 * on narrower, UI-shaped projections that mix that raw data with
 * derived state (heartbeat freshness, replay progress, history).
 *
 * Every summary is *immutable* and *referentially stable* — memoized
 * selectors return the same reference until the inputs change.
 */

import type { ClockSnapshot, ConnectionState, RuntimeStatus } from "@/types/runtime";
import type { ConnectionPhase } from "@/runtime/websocket";

/**
 * Coarse three-state visibility — what the operator sees at a glance.
 * Distinct from :type:`ConnectionPhase` (the rich enum) because the
 * compact badge only needs three colors.
 */
export type ConnectionVisibility = "live" | "transitional" | "offline" | "error";

export interface ConnectionPhaseSummary {
  /** Canonical websocket lifecycle phase. */
  phase: ConnectionPhase;
  /** Legacy connection-state projection for backward compatibility. */
  legacyState: ConnectionState;
  /** Human-readable label rendered in the badge. */
  label: string;
  /** Coarse visibility — used by the indicator + tooltip intent. */
  visibility: ConnectionVisibility;
  /** ``true`` when the websocket is connected + live. */
  isLive: boolean;
  /** ``true`` while attempting reconnect. */
  isReconnecting: boolean;
  /** ``true`` while initial hydration is in flight. */
  isHydrating: boolean;
  /** ``true`` while applying a replay batch. */
  isReplaying: boolean;
  /** ``true`` in any error / failed phase. */
  hasError: boolean;
}

export interface ReconnectSummary {
  /** Reconnect attempts since the last clean start. */
  attempts: number;
  /** ``true`` when more reconnects than the soft threshold occurred. */
  isFlaky: boolean;
}

export interface HeartbeatSummary {
  /** Monotonic ms of the last applied frame. ``null`` when none seen. */
  lastFrameAtMonotonicMs: number | null;
  /** ms since the last frame, computed against an injected ``nowMs``. */
  lastFrameAgoMs: number | null;
  /** ``true`` when no frame has landed within the freshness budget. */
  isStale: boolean;
  /** ``true`` when no frame has landed within the offline budget. */
  isOffline: boolean;
  /** Server-published uptime in seconds. */
  serverUptimeSeconds: number;
  /** Connected websocket clients reported by heartbeat. */
  connectedClients: number;
}

export interface HydrationSummary {
  /** Cumulative hydration count for this session. */
  hydrations: number;
  /** Last hydration duration in ms. */
  lastDurationMs: number;
  /** ``true`` when a hydration is currently in flight. */
  inFlight: boolean;
}

export interface ReplaySyncSummary {
  /** Snapshot covered the requested cursor. */
  windowHit: boolean;
  /** Lowest sequence the backend can satisfy. */
  oldestRetainedSequence: number | null;
  /** Highest sequence the backend can satisfy. */
  newestRetainedSequence: number | null;
  /** Current store sequence — the live cursor. */
  lastSequence: number;
  /** Replay-cursor progress in [0, 1]. */
  cursorProgress: number;
  /** ``true`` when the snapshot fell outside the retention window. */
  windowMissed: boolean;
}

export interface ConnectionSummary {
  /** Phase + visibility. */
  phase: ConnectionPhaseSummary;
  /** Reconnect attempts + flakiness flag. */
  reconnect: ReconnectSummary;
  /** Heartbeat freshness. */
  heartbeat: HeartbeatSummary;
  /** Snapshot hydration counters. */
  hydration: HydrationSummary;
  /** Replay window state. */
  replay: ReplaySyncSummary;
  /** Most recent clock snapshot. */
  clock: ClockSnapshot | null;
  /** Latest runtime status (idle/running/paused/stopped). */
  runtimeStatus: RuntimeStatus;
  /** Content signature for memoization. */
  signature: string;
}

/**
 * One entry in the connection-history ring buffer.
 *
 * The history is in-memory and bounded — operators use it to
 * understand a flaky session without persisting anything.
 */
export type ConnectionHistoryKind =
  | "phase_changed"
  | "hydration_started"
  | "hydration_completed"
  | "reconnect_attempted"
  | "replay_started"
  | "replay_completed"
  | "heartbeat_stale"
  | "protocol_error";

export interface ConnectionHistoryEntry {
  /** Monotonic ms at recording time. */
  atMonotonicMs: number;
  /** Wall-clock ms (best-effort, sourced from ``Date.now()``). */
  atWallMs: number;
  /** What changed. */
  kind: ConnectionHistoryKind;
  /** Phase observed at recording time. */
  phase: ConnectionPhase;
  /** Optional sequence cursor at recording time. */
  sequence: number | null;
  /** Reconnect attempts at recording time. */
  reconnectAttempts: number;
  /** Free-form one-line explanation. */
  detail: string;
}

/** Thresholds shared by selectors + tests. */
export const HEARTBEAT_STALE_MS = 5_000;
export const HEARTBEAT_OFFLINE_MS = 15_000;
export const FLAKY_RECONNECT_THRESHOLD = 3;
export const HISTORY_RING_CAPACITY = 64;
