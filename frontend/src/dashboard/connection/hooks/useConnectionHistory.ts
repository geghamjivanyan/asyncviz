/**
 * In-memory connection history.
 *
 * Subscribes to :func:`useConnectionSummary` and appends a history
 * entry whenever a meaningful field changes (phase, reconnect
 * attempts, hydration completion, heartbeat health, replay window).
 * The buffer is local to the React subtree — there's no global
 * singleton, so each consumer gets its own ring. The dashboard
 * mounts exactly one consumer (the diagnostics page), keeping the
 * memory footprint predictable.
 */

import { useEffect, useRef, useState } from "react";
import { appendHistory, clearHistory as resetHistory } from "@/dashboard/connection/models/history";
import type {
  ConnectionHistoryEntry,
  ConnectionSummary,
} from "@/dashboard/connection/models/state";
import { getConnectionMetrics } from "@/dashboard/connection/observability";

export interface ConnectionHistory {
  entries: readonly ConnectionHistoryEntry[];
  clear: () => void;
}

interface TrackedFields {
  phase: ConnectionSummary["phase"]["phase"];
  reconnectAttempts: number;
  hydrations: number;
  heartbeatStale: boolean;
  heartbeatOffline: boolean;
  replayWindowHit: boolean;
  isReplaying: boolean;
}

function takeTracked(summary: ConnectionSummary): TrackedFields {
  return {
    phase: summary.phase.phase,
    reconnectAttempts: summary.reconnect.attempts,
    hydrations: summary.hydration.hydrations,
    heartbeatStale: summary.heartbeat.isStale,
    heartbeatOffline: summary.heartbeat.isOffline,
    replayWindowHit: summary.replay.windowHit,
    isReplaying: summary.phase.isReplaying,
  };
}

export function useConnectionHistory(summary: ConnectionSummary): ConnectionHistory {
  const [entries, setEntries] = useState<readonly ConnectionHistoryEntry[]>([]);
  const trackedRef = useRef<TrackedFields | null>(null);

  useEffect(() => {
    const prev = trackedRef.current;
    const next = takeTracked(summary);
    const metrics = getConnectionMetrics();
    const sequence = summary.replay.lastSequence;
    const reconnectAttempts = summary.reconnect.attempts;
    const phase = summary.phase.phase;

    let updated = entries;
    let dirty = false;

    const push = (kind: ConnectionHistoryEntry["kind"], detail: string): void => {
      updated = appendHistory(updated, {
        kind,
        phase,
        sequence,
        reconnectAttempts,
        detail,
      });
      metrics.recordHistoryAppend();
      dirty = true;
    };

    if (prev === null) {
      push("phase_changed", `Initial phase: ${phase}`);
    } else {
      if (prev.phase !== next.phase) {
        push("phase_changed", `${prev.phase} → ${next.phase}`);
        metrics.recordPhaseTransition();
      }
      if (prev.reconnectAttempts < next.reconnectAttempts) {
        push("reconnect_attempted", `Attempt #${next.reconnectAttempts}`);
        metrics.recordReconnectAttempt();
      }
      if (prev.hydrations < next.hydrations) {
        push("hydration_completed", `Hydrated in ${summary.hydration.lastDurationMs.toFixed(0)}ms`);
        metrics.recordHydrationCompletion();
      }
      if (!prev.heartbeatStale && next.heartbeatStale) {
        push("heartbeat_stale", "Heartbeat stale");
        metrics.recordHeartbeatStale();
      }
      if (!prev.heartbeatOffline && next.heartbeatOffline) {
        push("heartbeat_stale", "Heartbeat offline");
        metrics.recordHeartbeatOffline();
      }
      if (prev.isReplaying !== next.isReplaying) {
        if (next.isReplaying) {
          push("replay_started", "Replay window opened");
        } else {
          push("replay_completed", "Replay window closed");
        }
        metrics.recordReplayTransition();
      }
      if (prev.replayWindowHit && !next.replayWindowHit) {
        push("protocol_error", "Replay window missed (cold restart)");
      }
    }

    trackedRef.current = next;
    if (dirty) setEntries(updated);
    // ``entries`` is intentionally omitted from deps — we only react
    // to summary changes and rebuild via the closure-captured array.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [summary]);

  const clear = (): void => setEntries(resetHistory());

  return { entries, clear };
}
