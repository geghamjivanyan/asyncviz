/**
 * In-memory ring buffer for the connection history.
 *
 * Tiny, deliberate scope: the buffer captures phase / hydration /
 * replay / heartbeat events so the diagnostics page can render a
 * session timeline. Persistence is *not* a goal — operators clear
 * the buffer by reloading the page.
 *
 * The ring is pure-functional: ``append`` returns a fresh array; the
 * subscriber pattern is owned by a higher layer. This keeps the
 * model unit-testable without a singleton.
 */

import {
  HISTORY_RING_CAPACITY,
  type ConnectionHistoryEntry,
  type ConnectionHistoryKind,
} from "@/dashboard/connection/models/state";
import type { ConnectionPhase } from "@/runtime/websocket";

export interface AppendArgs {
  kind: ConnectionHistoryKind;
  phase: ConnectionPhase;
  sequence: number | null;
  reconnectAttempts: number;
  detail: string;
  /** Optional monotonic-ms — defaults to ``performance.now()``. */
  atMonotonicMs?: number;
  /** Optional wall-ms — defaults to ``Date.now()``. */
  atWallMs?: number;
  /** Bounded capacity (default: :data:`HISTORY_RING_CAPACITY`). */
  capacity?: number;
}

export function appendHistory(
  history: readonly ConnectionHistoryEntry[],
  args: AppendArgs,
): ConnectionHistoryEntry[] {
  const capacity = args.capacity ?? HISTORY_RING_CAPACITY;
  const entry: ConnectionHistoryEntry = {
    atMonotonicMs:
      args.atMonotonicMs ?? (typeof performance !== "undefined" ? performance.now() : Date.now()),
    atWallMs: args.atWallMs ?? Date.now(),
    kind: args.kind,
    phase: args.phase,
    sequence: args.sequence,
    reconnectAttempts: args.reconnectAttempts,
    detail: args.detail,
  };
  const next: ConnectionHistoryEntry[] = [...history, entry];
  if (next.length > capacity) {
    return next.slice(next.length - capacity);
  }
  return next;
}

export function clearHistory(): ConnectionHistoryEntry[] {
  return [];
}
