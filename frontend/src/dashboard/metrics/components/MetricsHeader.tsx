/**
 * Canonical metrics header.
 *
 * Composes the runtime-summary cards inside a responsive grid wrapped
 * in a single ``<section role="region" aria-label="Runtime metrics">``.
 * The component is presentational — consumers pass an already-
 * projected snapshot. The container component
 * :class:`MetricsHeaderContainer` does the store wiring.
 *
 * The grid degrades gracefully:
 *   * narrow widths    → 2 columns
 *   * tablet widths    → 3-4 columns
 *   * desktop widths   → all 8 cards on one row
 */

import { cn } from "@/lib/cn";
import { MetricsGrid } from "@/dashboard/metrics/components/MetricsGrid";
import { RuntimeHealthCard } from "@/dashboard/metrics/components/RuntimeHealthCard";
import { ConnectionStatusCard } from "@/dashboard/metrics/components/ConnectionStatusCard";
import { ReplayStatusCard } from "@/dashboard/metrics/components/ReplayStatusCard";
import { WarningSummaryCard } from "@/dashboard/metrics/components/WarningSummaryCard";
import { TaskCountsCard } from "@/dashboard/metrics/components/TaskCountsCard";
import { ThroughputCard } from "@/dashboard/metrics/components/ThroughputCard";
import { EventRateCard } from "@/dashboard/metrics/components/EventRateCard";
import { RuntimeClockCard } from "@/dashboard/metrics/components/RuntimeClockCard";
import type { MetricsHeaderSnapshot } from "@/dashboard/metrics/models/summary";

export interface MetricsHeaderProps {
  snapshot: MetricsHeaderSnapshot;
  className?: string;
}

export function MetricsHeader({ snapshot, className }: MetricsHeaderProps) {
  return (
    <section
      role="region"
      aria-label="Runtime metrics"
      data-metrics-header="true"
      data-metrics-signature={snapshot.signature}
      className={cn(
        "flex w-full min-w-0 flex-col gap-2 border-b border-line bg-canvas px-4 py-3",
        className,
      )}
    >
      <MetricsGrid>
        <RuntimeHealthCard health={snapshot.health} />
        <ConnectionStatusCard connection={snapshot.connection} />
        <ReplayStatusCard replay={snapshot.replay} />
        <WarningSummaryCard warnings={snapshot.warnings} />
        <TaskCountsCard counts={snapshot.taskCounts} />
        <ThroughputCard throughput={snapshot.throughput} />
        <EventRateCard eventRate={snapshot.eventRate} />
        <RuntimeClockCard clock={snapshot.clock} connection={snapshot.connection} />
      </MetricsGrid>
    </section>
  );
}
