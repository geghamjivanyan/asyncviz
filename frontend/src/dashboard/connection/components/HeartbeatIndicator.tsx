/**
 * Heartbeat indicator — last-frame lag + freshness signal.
 */

import { memo } from "react";
import { cn } from "@/lib/cn";
import { formatLagMs } from "@/dashboard/connection/utils/format";
import type { HeartbeatSummary } from "@/dashboard/connection/models/state";
import { TEXT_PALETTE } from "@/ui/theme/tokens";

export interface HeartbeatIndicatorProps {
  heartbeat: HeartbeatSummary;
}

function HeartbeatIndicatorImpl({ heartbeat }: HeartbeatIndicatorProps) {
  const tone = heartbeat.isOffline
    ? TEXT_PALETTE.danger
    : heartbeat.isStale
      ? TEXT_PALETTE.warning
      : TEXT_PALETTE.subtle;
  const label =
    heartbeat.lastFrameAgoMs === null ? "no frames" : formatLagMs(heartbeat.lastFrameAgoMs);
  return (
    <div
      role="status"
      aria-label={`Heartbeat ${label}`}
      data-heartbeat-stale={heartbeat.isStale ? "true" : "false"}
      data-heartbeat-offline={heartbeat.isOffline ? "true" : "false"}
      className="flex min-w-0 items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest"
    >
      <span className="text-muted">hb</span>
      <span className={cn("tabular-nums", tone)}>{label}</span>
    </div>
  );
}

export const HeartbeatIndicator = memo(HeartbeatIndicatorImpl);
