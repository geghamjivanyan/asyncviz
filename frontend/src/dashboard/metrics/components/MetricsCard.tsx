/**
 * Generic card primitive for the metrics header.
 *
 * Each runtime-summary card composes this with one or more
 * :class:`MetricsBadge` / :class:`MetricsStatus` children. The card
 * stays semantic — ``role="group"`` with an ``aria-label`` so screen
 * readers can navigate the header by card.
 */

import { memo, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { INTENT_BORDER } from "@/ui/theme/tokens";
import type { Intent } from "@/ui/theme/tokens";
import { getMetricsHeaderMetrics } from "@/dashboard/metrics/observability";

export interface MetricsCardProps {
  /** Stable id used by tests + observability. */
  id: string;
  /** Visible label. */
  label: string;
  /** Border intent. */
  intent?: Intent;
  /** Loading state — replaces value with a placeholder. */
  loading?: boolean;
  /** Error state — replaces value with a danger placeholder. */
  errored?: boolean;
  /** Main value rendered in the centre of the card. */
  value?: ReactNode;
  /** Optional sub-label / trend / footer line. */
  detail?: ReactNode;
  /** Right-aligned slot (badge / status / sparkline). */
  trailing?: ReactNode;
  className?: string;
  /** Optional aria-describedby override. */
  ariaDescribedBy?: string;
}

function MetricsCardImpl({
  id,
  label,
  intent = "default",
  loading = false,
  errored = false,
  value,
  detail,
  trailing,
  className,
  ariaDescribedBy,
}: MetricsCardProps) {
  getMetricsHeaderMetrics().recordCardRender();
  const labelId = `metrics-card-${id}-label`;
  return (
    <article
      role="group"
      aria-labelledby={labelId}
      aria-describedby={ariaDescribedBy}
      data-metrics-card={id}
      data-loading={loading ? "true" : undefined}
      data-error={errored ? "true" : undefined}
      className={cn(
        "flex min-w-0 flex-col gap-1 rounded border bg-panel px-3 py-2",
        INTENT_BORDER[intent],
        errored && "border-danger",
        className,
      )}
    >
      <div className="flex min-w-0 items-center justify-between gap-2">
        <span
          id={labelId}
          className="truncate font-mono text-[10px] uppercase tracking-widest text-muted"
        >
          {label}
        </span>
        {trailing}
      </div>
      <div className="flex min-w-0 items-baseline gap-2">
        <span
          aria-live="polite"
          data-metrics-value="true"
          className={cn(
            "truncate font-mono text-base tabular-nums",
            errored ? "text-danger" : "text-text",
            loading && "opacity-50",
          )}
        >
          {loading ? "…" : (value ?? "—")}
        </span>
      </div>
      {detail !== undefined && (
        <div className="truncate font-mono text-[10px] uppercase tracking-widest text-subtle">
          {detail}
        </div>
      )}
    </article>
  );
}

export const MetricsCard = memo(MetricsCardImpl);
