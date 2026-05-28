/**
 * Renders the in-memory connection history ring.
 *
 * Items render oldest-first so operators can read a session timeline
 * top-to-bottom. The list is bounded by
 * :data:`HISTORY_RING_CAPACITY`; the parent owns the clear action.
 */

import { memo } from "react";
import { formatLagMs, formatWallTime } from "@/dashboard/connection/utils/format";
import type {
  ConnectionHistoryEntry,
  ConnectionHistoryKind,
} from "@/dashboard/connection/models/state";
import { cn } from "@/lib/cn";

const KIND_LABEL: Record<ConnectionHistoryKind, string> = {
  phase_changed: "phase",
  hydration_started: "hyd start",
  hydration_completed: "hyd done",
  reconnect_attempted: "reconnect",
  replay_started: "replay",
  replay_completed: "replay end",
  heartbeat_stale: "heartbeat",
  protocol_error: "error",
};

const KIND_TONE: Record<ConnectionHistoryKind, string> = {
  phase_changed: "text-accent",
  hydration_started: "text-muted",
  hydration_completed: "text-success",
  reconnect_attempted: "text-warning",
  replay_started: "text-accent",
  replay_completed: "text-muted",
  heartbeat_stale: "text-warning",
  protocol_error: "text-danger",
};

export interface ConnectionHistoryProps {
  entries: readonly ConnectionHistoryEntry[];
  onClear?: () => void;
  className?: string;
}

function ConnectionHistoryImpl({ entries, onClear, className }: ConnectionHistoryProps) {
  return (
    <section
      role="log"
      aria-label="Connection history"
      data-connection-history="true"
      className={cn("flex flex-col gap-2 font-mono text-[11px] text-muted", className)}
    >
      <header className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-widest text-muted">Connection history</span>
        {onClear && entries.length > 0 && (
          <button
            type="button"
            onClick={onClear}
            className="rounded border border-line px-1.5 py-0.5 text-[10px] uppercase tracking-widest text-subtle hover:border-accent hover:text-accent"
          >
            Clear
          </button>
        )}
      </header>
      {entries.length === 0 ? (
        <p className="text-[11px] text-subtle">No transitions recorded yet.</p>
      ) : (
        <ol className="flex flex-col gap-0.5">
          {entries.map((entry, index) => (
            <li
              key={`${entry.atMonotonicMs}-${index}`}
              data-history-kind={entry.kind}
              className="flex items-center gap-2"
            >
              <span className="shrink-0 tabular-nums text-subtle">
                {formatWallTime(entry.atWallMs)}
              </span>
              <span
                className={cn(
                  "shrink-0 rounded border border-line px-1.5 py-0.5 text-[9px] uppercase tracking-widest",
                  KIND_TONE[entry.kind],
                )}
              >
                {KIND_LABEL[entry.kind]}
              </span>
              <span className="truncate text-text">{entry.detail}</span>
              {entry.sequence !== null && (
                <span
                  aria-label={`Sequence ${entry.sequence}`}
                  className="ml-auto shrink-0 tabular-nums text-subtle"
                >
                  seq {entry.sequence}
                </span>
              )}
              {index > 0 && (
                <span
                  aria-label={`+${formatLagMs(entry.atMonotonicMs - entries[index - 1]!.atMonotonicMs)} since previous`}
                  className="sr-only"
                >
                  +{formatLagMs(entry.atMonotonicMs - entries[index - 1]!.atMonotonicMs)}
                </span>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

export const ConnectionHistory = memo(ConnectionHistoryImpl);
