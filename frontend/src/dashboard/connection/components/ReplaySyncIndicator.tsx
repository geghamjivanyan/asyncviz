/**
 * Replay-sync indicator — cursor position + window state.
 */

import { memo } from "react";
import { cn } from "@/lib/cn";
import { formatPercent, formatSequence } from "@/dashboard/connection/utils/format";
import type { ReplaySyncSummary } from "@/dashboard/connection/models/state";
import { TEXT_PALETTE } from "@/ui/theme/tokens";

export interface ReplaySyncIndicatorProps {
  replay: ReplaySyncSummary;
}

function ReplaySyncIndicatorImpl({ replay }: ReplaySyncIndicatorProps) {
  return (
    <div
      role="status"
      aria-label={`Replay cursor ${formatSequence(replay.lastSequence)} ${replay.windowMissed ? "cold restart" : "in window"}`}
      data-replay-window-hit={replay.windowHit ? "true" : "false"}
      data-replay-cursor-progress={replay.cursorProgress.toFixed(2)}
      className="flex min-w-0 items-center gap-2 font-mono text-[10px] uppercase tracking-widest"
    >
      <span className={cn("text-muted")}>cursor</span>
      <span className="tabular-nums text-text">{formatSequence(replay.lastSequence)}</span>
      <span className={cn(replay.windowMissed ? TEXT_PALETTE.danger : TEXT_PALETTE.muted)}>
        {replay.windowMissed ? "cold" : `${formatPercent(replay.cursorProgress)}`}
      </span>
    </div>
  );
}

export const ReplaySyncIndicator = memo(ReplaySyncIndicatorImpl);
