/**
 * Lifecycle summary row — first-seen / last-seen / recovered / counts.
 *
 * Stateless display: every value comes from the view model. Lives at
 * the top of the card so operators can see the freeze envelope without
 * expanding the drilldown.
 */

import { memo } from "react";
import type { BlockingWarningView } from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import {
  formatCount,
  formatDurationMs,
  formatLagMs,
} from "@/dashboard/warnings/blocking/utils/formatting";

export interface BlockingWarningLifecycleSummaryProps {
  view: BlockingWarningView;
  className?: string;
}

function BlockingWarningLifecycleSummaryImpl({
  view,
  className,
}: BlockingWarningLifecycleSummaryProps) {
  const recovered = view.recoveredNs ?? null;
  const expired = view.expiredNs ?? null;
  const recoveryLabel =
    expired !== null ? "Expired" : recovered !== null ? "Recovered" : "Last seen";

  return (
    <dl
      className={className}
      aria-label="Freeze window summary"
      data-testid="blocking-warning-lifecycle-summary"
    >
      <div className="flex flex-wrap gap-4 text-xs font-mono">
        <Metric label="Duration" value={formatDurationMs(view.freezeDurationMs)} />
        <Metric label="Peak lag" value={formatLagMs(view.peakLagMs)} />
        <Metric label="Last lag" value={formatLagMs(view.lastLagMs)} />
        <Metric label="Violations" value={formatCount(view.violationCount)} />
        <Metric label="Escalations" value={formatCount(view.escalationCount)} />
        <Metric label="Captures" value={formatCount(view.captureIds.length)} />
        <Metric label={recoveryLabel} value={view.isOpen ? "—" : "✓"} />
      </div>
    </dl>
  );
}

export const BlockingWarningLifecycleSummary = memo(BlockingWarningLifecycleSummaryImpl);

function MetricImpl({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <dt className="text-subtle uppercase tracking-wider text-[10px]">{label}</dt>
      <dd className="text-text">{value}</dd>
    </div>
  );
}

const Metric = memo(MetricImpl);
