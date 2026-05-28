/**
 * Canonical connection-status indicator.
 *
 * The compact badge is rendered inline in dashboard chrome. A
 * disclosure toggle reveals the full tooltip (phase + replay +
 * hydration + heartbeat). The widget is presentational only —
 * :class:`ConnectionStatusContainer` does the store wiring.
 *
 * The disclosure is implemented with native ``<details>`` semantics
 * via ``aria-expanded`` on the trigger + a positioned ``role="group"``
 * tooltip. The compact / detailed view share the same projection, so
 * the tooltip's data never disagrees with the badge.
 */

import { memo, useCallback, useState } from "react";
import { cn } from "@/lib/cn";
import { ConnectionStatusBadge } from "@/dashboard/connection/components/ConnectionStatusBadge";
import { ConnectionTooltip } from "@/dashboard/connection/components/ConnectionTooltip";
import type { ConnectionSummary } from "@/dashboard/connection/models/state";
import { getConnectionMetrics } from "@/dashboard/connection/observability";

export interface ConnectionStatusIndicatorProps {
  summary: ConnectionSummary;
  /** ``true`` to render only the badge — useful in tight chrome. */
  badgeOnly?: boolean;
  className?: string;
}

function ConnectionStatusIndicatorImpl({
  summary,
  badgeOnly = false,
  className,
}: ConnectionStatusIndicatorProps) {
  getConnectionMetrics().recordIndicatorRender();
  const [open, setOpen] = useState(false);
  const handleToggle = useCallback(() => setOpen((prev) => !prev), []);

  if (badgeOnly) {
    return <ConnectionStatusBadge phase={summary.phase} compact />;
  }

  return (
    <div
      data-connection-indicator="true"
      data-connection-phase={summary.phase.phase}
      className={cn("relative inline-flex items-center gap-1.5", className)}
    >
      <ConnectionStatusBadge phase={summary.phase} />
      <button
        type="button"
        aria-expanded={open}
        aria-controls={`connection-tooltip-${summary.phase.phase}`}
        aria-label={open ? "Hide connection details" : "Show connection details"}
        onClick={handleToggle}
        className="rounded border border-line px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest text-subtle hover:border-accent hover:text-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent"
      >
        {open ? "▴" : "▾"}
      </button>
      {open && (
        <div
          id={`connection-tooltip-${summary.phase.phase}`}
          className="absolute right-0 top-full z-20 mt-1"
        >
          <ConnectionTooltip summary={summary} id={`connection-tooltip-${summary.phase.phase}`} />
        </div>
      )}
    </div>
  );
}

export const ConnectionStatusIndicator = memo(ConnectionStatusIndicatorImpl);
