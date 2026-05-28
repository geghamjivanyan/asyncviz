/**
 * Bottom status bar for the dashboard.
 *
 * Today shows the websocket connection, the runtime status, and the
 * server-published metrics (events, clients, last sequence). The
 * surface is intentionally minimal — designed as the spot where
 * future live indicators (replay sync, snapshot health, warning
 * count) accumulate without crowding the header.
 *
 * Hidden when :class:`DashboardLayoutContext.statusBarVisible` is
 * false; consumers toggle that via :func:`useDashboardLayout`.
 */

import type { ReactNode } from "react";
import {
  useConnectedClients,
  useConnectionState,
  useEvents,
  useLastSequence,
  useWarningSeverityCounts,
} from "@/state/runtime";
import { useDashboardLayout } from "@/dashboard/layout/context/DashboardLayoutContext";
import type { ConnectionState } from "@/types/runtime";
import { cn } from "@/lib/cn";

export interface DashboardStatusBarProps {
  /** Right-aligned slot for page-specific live status widgets. */
  children?: ReactNode;
  className?: string;
}

const CONNECTION_DOT: Record<ConnectionState, string> = {
  idle: "bg-subtle",
  connecting: "bg-warning",
  open: "bg-success",
  closed: "bg-subtle",
  error: "bg-danger",
};

export function DashboardStatusBar({ children, className }: DashboardStatusBarProps) {
  const { statusBarVisible } = useDashboardLayout();
  const connection = useConnectionState();
  const lastSequence = useLastSequence();
  const events = useEvents();
  const connectedClients = useConnectedClients();
  const warnings = useWarningSeverityCounts();
  const warningTotal = warnings.info + warnings.warning + warnings.error + warnings.critical;

  if (!statusBarVisible) return null;

  return (
    <footer
      role="contentinfo"
      aria-label="Runtime status bar"
      className={cn(
        "flex h-7 shrink-0 items-center justify-between gap-4 border-t border-line bg-panel px-3 font-mono text-[0.7rem] uppercase tracking-widest text-subtle",
        className,
      )}
    >
      <div className="flex items-center gap-3">
        <span className="flex items-center gap-1.5">
          <span
            aria-hidden
            className={cn("inline-block h-2 w-2 rounded-full", CONNECTION_DOT[connection])}
          />
          <span>ws · {connection}</span>
        </span>
        <span>seq · {lastSequence}</span>
        <span>events · {events.length}</span>
        <span>clients · {connectedClients}</span>
      </div>
      <div className="flex items-center gap-3">
        {/* Live counters wired in Task 4.4. Replay-sync + snapshot age
            still reserve their slots for future tasks. */}
        <span aria-label="replay sync (pending)">replay · —</span>
        <span aria-label="snapshot (pending)">snapshot · —</span>
        <span aria-label={`Active warnings: ${warningTotal}`}>warnings · {warningTotal}</span>
        {children}
      </div>
    </footer>
  );
}
