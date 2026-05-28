/**
 * Compact horizontal timeline view of the connection history.
 *
 * Each entry renders as a colored cell — width proportional to the
 * dwell time between entries. Decorative only; the canonical source
 * of truth is :class:`ConnectionHistory`. The component is therefore
 * marked ``aria-hidden`` and pairs with the textual history above it.
 */

import { memo } from "react";
import { cn } from "@/lib/cn";
import type {
  ConnectionHistoryEntry,
  ConnectionHistoryKind,
} from "@/dashboard/connection/models/state";

const KIND_COLOR: Record<ConnectionHistoryKind, string> = {
  phase_changed: "bg-accent",
  hydration_started: "bg-line",
  hydration_completed: "bg-success",
  reconnect_attempted: "bg-warning",
  replay_started: "bg-accent",
  replay_completed: "bg-line",
  heartbeat_stale: "bg-warning",
  protocol_error: "bg-danger",
};

export interface ConnectionTimelineProps {
  entries: readonly ConnectionHistoryEntry[];
  className?: string;
}

function ConnectionTimelineImpl({ entries, className }: ConnectionTimelineProps) {
  if (entries.length === 0) return null;
  const first = entries[0]!.atMonotonicMs;
  const last = entries[entries.length - 1]!.atMonotonicMs;
  const span = Math.max(1, last - first);
  return (
    <div
      aria-hidden="true"
      data-connection-timeline="true"
      className={cn("flex h-2 w-full overflow-hidden rounded border border-line", className)}
    >
      {entries.map((entry, index) => {
        const next = entries[index + 1]?.atMonotonicMs ?? last;
        const widthFraction = Math.max(0.05, (next - entry.atMonotonicMs) / span);
        return (
          <span
            key={`${entry.atMonotonicMs}-${index}`}
            data-history-kind={entry.kind}
            title={entry.detail}
            style={{ width: `${(widthFraction * 100).toFixed(2)}%` }}
            className={cn("h-full", KIND_COLOR[entry.kind])}
          />
        );
      })}
    </div>
  );
}

export const ConnectionTimeline = memo(ConnectionTimelineImpl);
