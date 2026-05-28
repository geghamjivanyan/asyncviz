/**
 * Tooltip with the full connection breakdown — phase + replay +
 * hydration + heartbeat + clock.
 *
 * Hover/focus-driven disclosure is owned by the parent indicator;
 * this component is purely presentational so it can also be embedded
 * directly into the diagnostics page.
 */

import { memo } from "react";
import { cn } from "@/lib/cn";
import { ConnectionPhaseIndicator } from "@/dashboard/connection/components/ConnectionPhaseIndicator";
import { ReplaySyncIndicator } from "@/dashboard/connection/components/ReplaySyncIndicator";
import { HydrationIndicator } from "@/dashboard/connection/components/HydrationIndicator";
import { HeartbeatIndicator } from "@/dashboard/connection/components/HeartbeatIndicator";
import type { ConnectionSummary } from "@/dashboard/connection/models/state";
import { getConnectionMetrics } from "@/dashboard/connection/observability";

export interface ConnectionTooltipProps {
  summary: ConnectionSummary;
  className?: string;
  /** Optional id used for ``aria-labelledby`` wiring. */
  id?: string;
}

function ConnectionTooltipImpl({ summary, className, id }: ConnectionTooltipProps) {
  getConnectionMetrics().recordTooltipRender();
  const headingId = id ? `${id}-heading` : undefined;
  return (
    <section
      role="group"
      aria-labelledby={headingId}
      data-connection-tooltip="true"
      className={cn(
        "flex w-72 flex-col gap-2 rounded border border-line bg-panel p-3 text-text shadow",
        className,
      )}
    >
      {headingId && (
        <span id={headingId} className="font-mono text-[10px] uppercase tracking-widest text-muted">
          Connection
        </span>
      )}
      <ConnectionPhaseIndicator phase={summary.phase} reconnect={summary.reconnect} />
      <div className="flex flex-wrap gap-x-3 gap-y-1 border-t border-line pt-2">
        <ReplaySyncIndicator replay={summary.replay} />
        <HydrationIndicator hydration={summary.hydration} />
        <HeartbeatIndicator heartbeat={summary.heartbeat} />
      </div>
      <dl className="flex flex-wrap gap-x-3 gap-y-0.5 border-t border-line pt-2 font-mono text-[10px] uppercase tracking-widest text-subtle">
        <span className="inline-flex items-center gap-1">
          <dt className="text-muted">clients</dt>
          <dd className="tabular-nums text-text">{summary.heartbeat.connectedClients}</dd>
        </span>
        <span className="inline-flex items-center gap-1">
          <dt className="text-muted">runtime</dt>
          <dd className="text-text">{summary.runtimeStatus}</dd>
        </span>
        {summary.clock && (
          <span className="inline-flex items-center gap-1">
            <dt className="text-muted">uptime</dt>
            <dd className="tabular-nums text-text">{Math.floor(summary.clock.uptime_seconds)}s</dd>
          </span>
        )}
      </dl>
    </section>
  );
}

export const ConnectionTooltip = memo(ConnectionTooltipImpl);
