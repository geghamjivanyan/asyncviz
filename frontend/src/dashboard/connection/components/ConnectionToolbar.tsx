/**
 * One-line toolbar — every sub-indicator in a single row.
 *
 * Used in the status bar / future overlay surfaces; carries the same
 * data as the tooltip but laid out horizontally.
 */

import { memo } from "react";
import { cn } from "@/lib/cn";
import { ConnectionPhaseIndicator } from "@/dashboard/connection/components/ConnectionPhaseIndicator";
import { ReplaySyncIndicator } from "@/dashboard/connection/components/ReplaySyncIndicator";
import { HydrationIndicator } from "@/dashboard/connection/components/HydrationIndicator";
import { HeartbeatIndicator } from "@/dashboard/connection/components/HeartbeatIndicator";
import type { ConnectionSummary } from "@/dashboard/connection/models/state";

export interface ConnectionToolbarProps {
  summary: ConnectionSummary;
  className?: string;
}

function ConnectionToolbarImpl({ summary, className }: ConnectionToolbarProps) {
  return (
    <div
      role="toolbar"
      aria-label="Connection diagnostics"
      data-connection-toolbar="true"
      className={cn("flex flex-wrap items-center gap-x-4 gap-y-1", className)}
    >
      <ConnectionPhaseIndicator phase={summary.phase} reconnect={summary.reconnect} />
      <ReplaySyncIndicator replay={summary.replay} />
      <HydrationIndicator hydration={summary.hydration} />
      <HeartbeatIndicator heartbeat={summary.heartbeat} />
    </div>
  );
}

export const ConnectionToolbar = memo(ConnectionToolbarImpl);
