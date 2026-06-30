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
  const detail = (
    <span className="flex min-w-0 items-baseline gap-x-2 truncate">
      <CountChip color={counts.active > 0 ? "text-success" : "text-subtle"} value={counts.active} label="running" />
      <Sep />
      <CountChip color={counts.waiting > 0 ? "text-accent" : "text-subtle"} value={counts.waiting} label="waiting" />
      <Sep />
      <CountChip color="text-subtle" value={counts.completed} label="done" />
      <Sep />
      <CountChip
        color={counts.failed > 0 ? "text-danger" : "text-subtle"}
        value={counts.failed}
        label="failed"
      />
    </span>
  );
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

function CountChip({
  color,
  value,
  label,
}: {
  color: string;
  value: number;
  label: string;
}) {
  return (
    <span className="inline-flex items-baseline gap-1">
      <span className={`font-mono text-xs tabular-nums ${color}`}>{formatCount(value)}</span>
      <span className="text-[10px] uppercase tracking-widest text-muted">{label}</span>
    </span>
  );
}

function Sep() {
  return (
    <span aria-hidden="true" className="text-subtle">
      ·
    </span>
  );
}

export const TaskCountsCard = memo(TaskCountsCardImpl);
