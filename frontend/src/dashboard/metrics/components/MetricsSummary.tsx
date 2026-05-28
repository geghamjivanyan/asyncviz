/**
 * One-line summary for dense layouts (status bar, compact mode).
 *
 * Renders the same data as the full header but as a dl row — no
 * cards, no badges. Suitable for the bottom status bar or future
 * tooltip layouts.
 */

import { memo } from "react";
import { cn } from "@/lib/cn";
import { formatCount, formatRate } from "@/dashboard/metrics/utils/format";
import type { MetricsHeaderSnapshot } from "@/dashboard/metrics/models/summary";

export interface MetricsSummaryProps {
  snapshot: MetricsHeaderSnapshot;
  className?: string;
}

function MetricsSummaryImpl({ snapshot, className }: MetricsSummaryProps) {
  return (
    <dl
      role="group"
      aria-label="Runtime summary"
      data-metrics-summary="true"
      className={cn(
        "flex items-center gap-3 font-mono text-[0.7rem] uppercase tracking-widest text-subtle",
        className,
      )}
    >
      <Item label="health" value={snapshot.health.label} />
      <Item label="stream" value={snapshot.connection.phase} />
      <Item label="tasks" value={formatCount(snapshot.taskCounts.total)} />
      <Item label="rate" value={formatRate(snapshot.eventRate.envelopesPerSecond)} />
      <Item label="warn" value={formatCount(snapshot.warnings.total)} />
    </dl>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="sr-only">{label}</dt>
      <dd>
        {label} · {value}
      </dd>
    </>
  );
}

export const MetricsSummary = memo(MetricsSummaryImpl);
