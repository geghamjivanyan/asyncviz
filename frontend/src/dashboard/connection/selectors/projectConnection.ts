/**
 * Pure projection: store state → :type:`ConnectionSummary`.
 *
 * Functions here are pure (no React, no Zustand) so they're testable
 * in isolation. Hooks higher up the stack memoize the result.
 */

import type { ClockSnapshot, ConnectionState, RuntimeStatus } from "@/types/runtime";
import {
  isConnectingPhase,
  isLivePhase,
  isTerminalPhase,
  toConnectionState,
  type ConnectionPhase,
} from "@/runtime/websocket";
import type { ConnectionMeta, ReconciliationStats, ReplayMeta, RuntimeMeta } from "@/state/runtime";
import {
  FLAKY_RECONNECT_THRESHOLD,
  HEARTBEAT_OFFLINE_MS,
  HEARTBEAT_STALE_MS,
  type ConnectionPhaseSummary,
  type ConnectionSummary,
  type ConnectionVisibility,
  type HeartbeatSummary,
  type HydrationSummary,
  type ReconnectSummary,
  type ReplaySyncSummary,
} from "@/dashboard/connection/models/state";

export interface ConnectionProjectionInputs {
  connection: ConnectionMeta;
  runtime: RuntimeMeta;
  replay: ReplayMeta;
  stats: ReconciliationStats;
  lastSequence: number;
  /** ``performance.now()`` — injected for testability. */
  nowMs: number;
  /** ``true`` while hydration is in flight (start has fired, completion hasn't). */
  hydrationInFlight: boolean;
}

const PHASE_LABEL: Record<ConnectionPhase, string> = {
  idle: "Disconnected",
  hydrating: "Hydrating",
  connecting: "Connecting",
  replaying: "Replaying",
  live: "Live",
  reconnecting: "Reconnecting",
  disconnected: "Disconnected",
  failed: "Failed",
};

const PHASE_VISIBILITY: Record<ConnectionPhase, ConnectionVisibility> = {
  idle: "offline",
  hydrating: "transitional",
  connecting: "transitional",
  replaying: "transitional",
  live: "live",
  reconnecting: "transitional",
  disconnected: "offline",
  failed: "error",
};

export function projectPhase(inputs: ConnectionProjectionInputs): ConnectionPhaseSummary {
  const phase = inputs.connection.phase;
  const legacy: ConnectionState = inputs.connection.state ?? toConnectionState(phase);
  const label = labelFor(phase, inputs.runtime);
  return {
    phase,
    legacyState: legacy,
    label,
    visibility: PHASE_VISIBILITY[phase] ?? "offline",
    isLive: isLivePhase(phase),
    isReconnecting: phase === "reconnecting",
    isHydrating: isConnectingPhase(phase) || inputs.hydrationInFlight,
    // A live connection in replay mode still drives a replay-aware
    // label; consumers that branch on ``isReplaying`` (timeline /
    // diagnostics chips) light up either when the connection is
    // mid-replay-handshake OR when replay mode has been observed
    // on the wire.
    isReplaying: phase === "replaying" || inputs.runtime.replayActive,
    hasError: isTerminalPhase(phase) && phase === "failed",
  };
}

/**
 * Resolve the operator-facing badge text.
 *
 * Replay mode overrides the live-mode labels once the SPA has
 * observed a ``replay_status`` envelope. The playback state then
 * decides between REPLAY / PAUSED / STOPPED / replay-specific
 * transient states so the badge never says "Live" while
 * showing recorded data.
 */
function labelFor(phase: ConnectionPhase, runtime: RuntimeMeta): string {
  if (runtime.replayActive && isLivePhase(phase)) {
    const playback = runtime.replayPlaybackState;
    if (playback === "paused") return "Paused";
    if (playback === "stopped") return "Stopped";
    if (playback === "seeking") return "Seeking";
    if (playback === "buffering") return "Buffering";
    if (playback === "failed") return "Failed";
    // ``playing`` / ``idle`` / null → operator-facing "Replay".
    return "Replay";
  }
  return PHASE_LABEL[phase] ?? phase;
}

export function projectReconnect(inputs: ConnectionProjectionInputs): ReconnectSummary {
  const attempts = inputs.connection.reconnectAttempts;
  return {
    attempts,
    isFlaky: attempts >= FLAKY_RECONNECT_THRESHOLD,
  };
}

export function projectHeartbeat(inputs: ConnectionProjectionInputs): HeartbeatSummary {
  const last = inputs.connection.lastFrameAtMonotonicMs;
  const lastFrameAtMonotonicMs = last > 0 ? last : null;
  const lastFrameAgoMs =
    lastFrameAtMonotonicMs === null ? null : Math.max(0, inputs.nowMs - lastFrameAtMonotonicMs);
  const isStale = lastFrameAgoMs !== null && lastFrameAgoMs >= HEARTBEAT_STALE_MS;
  const isOffline = lastFrameAgoMs !== null && lastFrameAgoMs >= HEARTBEAT_OFFLINE_MS;
  return {
    lastFrameAtMonotonicMs,
    lastFrameAgoMs,
    isStale,
    isOffline,
    serverUptimeSeconds: inputs.runtime.serverUptimeSeconds,
    connectedClients: inputs.runtime.connectedClients,
  };
}

export function projectHydration(inputs: ConnectionProjectionInputs): HydrationSummary {
  return {
    hydrations: inputs.stats.hydrations,
    lastDurationMs: inputs.stats.lastHydrationDurationMs,
    inFlight: inputs.hydrationInFlight,
  };
}

export function projectReplaySync(inputs: ConnectionProjectionInputs): ReplaySyncSummary {
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
    cursorProgress,
    windowMissed: !inputs.replay.windowHit,
  };
}

export function projectConnection(inputs: ConnectionProjectionInputs): ConnectionSummary {
  const phase = projectPhase(inputs);
  const reconnect = projectReconnect(inputs);
  const heartbeat = projectHeartbeat(inputs);
  const hydration = projectHydration(inputs);
  const replay = projectReplaySync(inputs);
  const runtimeStatus: RuntimeStatus = inputs.runtime.status;
  const clock: ClockSnapshot | null = inputs.runtime.clock;
  const signature = sign(phase, reconnect, heartbeat, hydration, replay, runtimeStatus, clock);
  return {
    phase,
    reconnect,
    heartbeat,
    hydration,
    replay,
    clock,
    runtimeStatus,
    signature,
  };
}

function sign(
  phase: ConnectionPhaseSummary,
  reconnect: ReconnectSummary,
  heartbeat: HeartbeatSummary,
  hydration: HydrationSummary,
  replay: ReplaySyncSummary,
  runtimeStatus: RuntimeStatus,
  clock: ClockSnapshot | null,
): string {
  // Bucket the heartbeat lag at 250ms so a sub-quantum tick doesn't
  // force a re-render — visible diff is still preserved.
  const lagBucket =
    heartbeat.lastFrameAgoMs === null ? "" : String(Math.floor(heartbeat.lastFrameAgoMs / 250));
  return [
    phase.phase,
    phase.label,
    phase.visibility,
    reconnect.attempts,
    reconnect.isFlaky ? 1 : 0,
    lagBucket,
    heartbeat.isStale ? 1 : 0,
    heartbeat.isOffline ? 1 : 0,
    heartbeat.connectedClients,
    hydration.hydrations,
    Math.round(hydration.lastDurationMs),
    hydration.inFlight ? 1 : 0,
    replay.windowHit ? 1 : 0,
    replay.lastSequence,
    replay.newestRetainedSequence ?? "",
    Math.round(replay.cursorProgress * 1000),
    runtimeStatus,
    clock === null ? "" : Math.round(clock.uptime_seconds),
  ].join("|");
}
