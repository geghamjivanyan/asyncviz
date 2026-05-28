/**
 * Compact header strip showing live counts + cumulative stats.
 *
 * Reads the snapshot's ``statistics`` + ``metrics`` blocks. Rendered
 * above the filter bar so operators see the runtime-level picture at
 * a glance before drilling into individual warnings.
 *
 * The freeze duration / peak lag values come from the statistics
 * block; counts come from the per-store summary. Both are formatted
 * via :func:`formatDurationMs` for consistency with the cards.
 */

import { memo } from "react";
import { Badge } from "@/ui/primitives/Badge";
import { cn } from "@/lib/cn";
import { formatCount, formatDurationMs } from "@/dashboard/warnings/blocking/utils/formatting";
import type {
  BlockingGroupSeverity,
  BlockingWarningEmitterMetricsModel,
  BlockingWarningEmitterStatisticsModel,
} from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import type {
  BlockingWarningCounts,
} from "@/dashboard/warnings/blocking/selectors/BlockingWarningSelectors";

export interface BlockingWarningMetricsHeaderProps {
  counts: BlockingWarningCounts;
  statistics: BlockingWarningEmitterStatisticsModel | null;
  metrics: BlockingWarningEmitterMetricsModel | null;
  className?: string;
}

const SEVERITY_COLOR: Record<BlockingGroupSeverity, "default" | "warning" | "danger"> = {
  NONE: "default",
  WARNING: "warning",
  CRITICAL: "danger",
  FREEZE: "danger",
};

function BlockingWarningMetricsHeaderImpl({
  counts,
  statistics,
  metrics,
  className,
}: BlockingWarningMetricsHeaderProps) {
  return (
    <div
      className={cn("flex flex-wrap items-center gap-3 text-xs font-mono", className)}
      aria-label="Blocking warning summary"
      data-testid="blocking-warning-metrics-header"
    >
      <Badge intent="default" aria-label="Active warning count">
        Active: {formatCount(counts.active)}
      </Badge>
      <Badge intent="default" aria-label="Recovered warning count">
        Recovered: {formatCount(counts.recovered)}
      </Badge>
      {(["FREEZE", "CRITICAL", "WARNING"] as const).map((severity) =>
        counts.bySeverity[severity] > 0 ? (
          <Badge
            key={severity}
            intent={SEVERITY_COLOR[severity]}
            aria-label={`${severity} count`}
            data-testid={`blocking-warning-count-${severity.toLowerCase()}`}
          >
            {severity}: {formatCount(counts.bySeverity[severity])}
          </Badge>
        ) : null,
      )}
      {statistics !== null && (
        <span className="text-subtle" data-testid="blocking-warning-longest-freeze">
          longest:{" "}
          <span className="text-text">
            {formatDurationMs(statistics.longest_freeze_duration_ns / 1_000_000)}
          </span>
        </span>
      )}
      {statistics !== null && (
        <span className="text-subtle" data-testid="blocking-warning-peak-lag">
          peak lag:{" "}
          <span className="text-text">
            {formatDurationMs(statistics.peak_lag_ns / 1_000_000)}
          </span>
        </span>
      )}
      {metrics !== null && (
        <span className="text-subtle" data-testid="blocking-warning-emitter-stats">
          emitted: <span className="text-text">{formatCount(metrics.events_emitted)}</span>
          {" · "}
          suppressed:{" "}
          <span className="text-text">
            {formatCount(metrics.suppressed_by_dedup + metrics.suppressed_by_policy)}
          </span>
        </span>
      )}
    </div>
  );
}

export const BlockingWarningMetricsHeader = memo(BlockingWarningMetricsHeaderImpl);
