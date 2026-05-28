/**
 * Task-counts card — active + terminal breakdown.
 */

import { memo } from "react";
import { MetricsCard } from "@/dashboard/metrics/components/MetricsCard";
import { MetricsBadge } from "@/dashboard/metrics/components/MetricsBadge";
import { formatCount } from "@/dashboard/metrics/utils/format";
import type { Intent } from "@/ui/theme/tokens";
import type { TaskCountSummary } from "@/dashboard/metrics/models/summary";

export interface TaskCountsCardProps {
  counts: TaskCountSummary;
}

function TaskCountsCardImpl({ counts }: TaskCountsCardProps) {
  const intent: Intent = counts.failed > 0 ? "danger" : counts.active > 0 ? "success" : "default";
  const detail = `run ${formatCount(counts.active)} · wait ${formatCount(counts.waiting)} · done ${formatCount(
    counts.completed,
  )} · fail ${formatCount(counts.failed)}`;
  return (
    <MetricsCard
      id="task-counts"
      label="Tasks"
      intent={intent}
      value={formatCount(counts.total)}
      trailing={<MetricsBadge intent={intent}>{formatCount(counts.active)} live</MetricsBadge>}
      detail={detail}
    />
  );
}

export const TaskCountsCard = memo(TaskCountsCardImpl);
