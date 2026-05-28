/**
 * Warning-summary card.
 *
 * Aggregates active warnings by severity into a single count + a
 * highest-severity badge. The card border promotes to the matching
 * danger / warning intent so the row stays glanceable.
 */

import { memo } from "react";
import { MetricsCard } from "@/dashboard/metrics/components/MetricsCard";
import { MetricsBadge } from "@/dashboard/metrics/components/MetricsBadge";
import { formatCount } from "@/dashboard/metrics/utils/format";
import type { Intent } from "@/ui/theme/tokens";
import type { WarningSeverity } from "@/types/runtime";
import type { WarningSummary } from "@/dashboard/metrics/models/summary";

const SEVERITY_INTENT: Record<WarningSeverity, Intent> = {
  info: "accent",
  warning: "warning",
  error: "danger",
  critical: "danger",
};

export interface WarningSummaryCardProps {
  warnings: WarningSummary;
}

function WarningSummaryCardImpl({ warnings }: WarningSummaryCardProps) {
  const highest = warnings.highest;
  const intent: Intent = highest === null ? "default" : SEVERITY_INTENT[highest];
  const counts = warnings.countsBySeverity;
  const detail =
    warnings.total === 0
      ? "No active warnings"
      : `C ${counts.critical} · E ${counts.error} · W ${counts.warning} · I ${counts.info}`;
  return (
    <MetricsCard
      id="warning-summary"
      label="Warnings"
      intent={intent}
      value={formatCount(warnings.total)}
      trailing={
        <MetricsBadge
          intent={intent}
          ariaLabel={highest === null ? "No active warnings" : `Highest active severity ${highest}`}
        >
          {highest ?? "ok"}
        </MetricsBadge>
      }
      detail={detail}
    />
  );
}

export const WarningSummaryCard = memo(WarningSummaryCardImpl);
