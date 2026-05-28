/**
 * Hydration indicator — surfaces hydration count + last duration.
 */

import { memo } from "react";
import { formatDurationMs } from "@/dashboard/connection/utils/format";
import type { HydrationSummary } from "@/dashboard/connection/models/state";

export interface HydrationIndicatorProps {
  hydration: HydrationSummary;
}

function HydrationIndicatorImpl({ hydration }: HydrationIndicatorProps) {
  return (
    <div
      role="status"
      aria-label={`Hydrations ${hydration.hydrations}`}
      data-hydration-in-flight={hydration.inFlight ? "true" : "false"}
      className="flex min-w-0 items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-muted"
    >
      <span>hyd</span>
      <span className="tabular-nums text-text">{hydration.hydrations}</span>
      {hydration.lastDurationMs > 0 && (
        <span className="tabular-nums text-subtle">
          {formatDurationMs(hydration.lastDurationMs)}
        </span>
      )}
      {hydration.inFlight && <span className="text-accent">…</span>}
    </div>
  );
}

export const HydrationIndicator = memo(HydrationIndicatorImpl);
