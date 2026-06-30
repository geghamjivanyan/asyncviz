/**
 * Replay-status card.
 *
 * Renders the replay window state — whether the snapshot satisfied
 * the cursor, the cursor position, and the replay-window range.
 */

import { memo } from "react";
import { MetricsCard } from "@/dashboard/metrics/components/MetricsCard";
import { MetricsBadge } from "@/dashboard/metrics/components/MetricsBadge";
import { formatPercent, formatSequence } from "@/dashboard/metrics/utils/format";
import type { Intent } from "@/ui/theme/tokens";
import type { ReplaySummary } from "@/dashboard/metrics/models/summary";

export interface ReplayStatusCardProps {
  replay: ReplaySummary;
}

function ReplayStatusCardImpl({ replay }: ReplayStatusCardProps) {
  const intent: Intent = !replay.windowHit ? "warning" : replay.isReplaying ? "accent" : "default";
  const badgeLabel = !replay.windowHit
    ? "Cold restart"
    : replay.isReplaying
      ? "Replaying"
      : "In window";
  const oldest = formatSequence(replay.oldestRetainedSequence);
  const newest = formatSequence(replay.newestRetainedSequence);
  const hasRange = replay.oldestRetainedSequence !== null && replay.newestRetainedSequence !== null;
  const detail = hasRange ? `Buffered events #${oldest}–#${newest}` : "No events buffered yet";
  return (
    <MetricsCard
      id="replay-status"
      label="Replay buffer"
      intent={intent}
      value={`Event #${formatSequence(replay.lastSequence)} · ${formatPercent(replay.cursorProgress)}`}
      trailing={
        <MetricsBadge
          intent={intent}
          ariaLabel={`Replay state ${badgeLabel}`}
          pulse={replay.isReplaying}
        >
          {badgeLabel}
        </MetricsBadge>
      }
      detail={detail}
    />
  );
}

export const ReplayStatusCard = memo(ReplayStatusCardImpl);
