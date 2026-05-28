/**
 * Canonical websocket-client lifecycle.
 *
 * The :enum:`ConnectionPhase` is monotonic during a normal session,
 * but a reconnect cycle loops back from ``LIVE`` → ``RECONNECTING`` →
 * ``CONNECTING`` → ``LIVE`` again. The legacy
 * ``ConnectionState`` string ("idle" | "connecting" | "open" |
 * "closed" | "error") is derived from the phase for backward
 * compatibility with the existing Zustand store.
 */

import type { ConnectionState } from "@/types/runtime";

export type ConnectionPhase =
  | "idle"
  | "hydrating"
  | "connecting"
  | "replaying"
  | "live"
  | "reconnecting"
  | "disconnected"
  | "failed";

const PHASE_ORDER: Record<ConnectionPhase, number> = {
  idle: 0,
  hydrating: 1,
  connecting: 2,
  replaying: 3,
  live: 4,
  reconnecting: 5,
  disconnected: 6,
  failed: 7,
};

export function phaseRank(phase: ConnectionPhase): number {
  return PHASE_ORDER[phase];
}

export function isTerminalPhase(phase: ConnectionPhase): boolean {
  return phase === "failed" || phase === "disconnected";
}

export function isLivePhase(phase: ConnectionPhase): boolean {
  return phase === "live" || phase === "replaying";
}

export function isConnectingPhase(phase: ConnectionPhase): boolean {
  return phase === "hydrating" || phase === "connecting" || phase === "reconnecting";
}

/**
 * Project the rich :enum:`ConnectionPhase` down to the simpler
 * :type:`ConnectionState` the Zustand store expects today. Used by
 * :class:`RuntimeWebSocketClient` so existing UI keeps working
 * without a store schema change.
 */
export function toConnectionState(phase: ConnectionPhase): ConnectionState {
  switch (phase) {
    case "idle":
    case "disconnected":
      return "idle";
    case "hydrating":
    case "connecting":
    case "reconnecting":
      return "connecting";
    case "replaying":
    case "live":
      return "open";
    case "failed":
      return "error";
  }
}
