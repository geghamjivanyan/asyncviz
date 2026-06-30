/**
 * Throughput card.
 *
 * Renders the aggregate ``tasks_per_second`` over the latest window,
 * and shows the failure / cancel rates as the detail.
 */

import { memo } from "react";
import { MetricsCard } from "@/dashboard/metrics/components/MetricsCard";
import { MetricsBadge } from "@/dashboard/metrics/components/MetricsBadge";
import { formatRate } from "@/dashboard/metrics/utils/format";
import type { ThroughputSummary } from "@/dashboard/metrics/models/summary";

export interface ThroughputCardProps {
  throughput: ThroughputSummary;
}

function ThroughputCardImpl({ throughput }: ThroughputCardProps) {
  const detail =
    throughput.windowSeconds > 0
      ? `Completed ${formatRate(throughput.completionsPerSecond)} · Failed ${formatRate(
          throughput.failuresPerSecond,
        )}`
      : "Waiting for samples";
  return (
    <MetricsCard
      id="throughput"
      label="Task throughput"
      value={`${formatRate(throughput.tasksPerSecond)}`}
      trailing={<MetricsBadge intent="accent">tasks/sec</MetricsBadge>}
      detail={detail}
    />
  );
}

export const ThroughputCard = memo(ThroughputCardImpl);
