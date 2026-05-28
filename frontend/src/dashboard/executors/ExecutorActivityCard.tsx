/**
 * Single-executor summary card.
 *
 * Stateless — driven by an :type:`ExecutorActivityView` + select callback.
 */

import { memo, useCallback } from "react";
import { cn } from "@/lib/cn";
import type { ExecutorActivityView } from "@/dashboard/executors/models/ExecutorActivityModels";
import { describeExecutorForAccessibility } from "@/dashboard/executors/ExecutorActivityAccessibility";
import { severityLabel } from "@/dashboard/executors/ExecutorActivitySeverity";

export interface ExecutorActivityCardProps {
  view: ExecutorActivityView;
  selected?: boolean;
  onSelect?: (executorId: string) => void;
  className?: string;
}

function formatRatio(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatRate(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0/s";
  if (value >= 100) return `${value.toFixed(0)}/s`;
  if (value >= 10) return `${value.toFixed(1)}/s`;
  return `${value.toFixed(2)}/s`;
}

function formatSeconds(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0s";
  if (value >= 1) return `${value.toFixed(2)}s`;
  if (value >= 0.001) return `${(value * 1000).toFixed(1)}ms`;
  return `${(value * 1_000_000).toFixed(0)}µs`;
}

function ExecutorActivityCardImpl({
  view,
  selected = false,
  onSelect,
  className,
}: ExecutorActivityCardProps): JSX.Element {
  const handleClick = useCallback(() => {
    onSelect?.(view.executorId);
  }, [view.executorId, onSelect]);

  return (
    <button
      type="button"
      data-testid="executor-activity-card"
      data-severity={view.severity}
      data-saturated={view.saturated ? "true" : undefined}
      data-executor-id={view.executorId}
      data-executor-kind={view.executorKind}
      onClick={handleClick}
      aria-pressed={selected}
      aria-label={describeExecutorForAccessibility(view)}
      className={cn(
        "executor-activity-card",
        selected && "executor-activity-card--selected",
        className,
      )}
    >
      <div className="executor-activity-card__header">
        <span className="executor-activity-card__name">{view.displayName}</span>
        <span className="executor-activity-card__kind">{view.executorKind}</span>
        <span className="executor-activity-card__severity">
          {severityLabel(view.severity)}
        </span>
      </div>
      <div className="executor-activity-card__row">
        <span className="executor-activity-card__metric">
          <span className="executor-activity-card__metric-label">workers</span>
          <span className="executor-activity-card__metric-value">
            {view.activeWorkers}
            {view.maxWorkers !== null && (
              <span className="executor-activity-card__metric-divisor">
                /{view.maxWorkers}
              </span>
            )}
          </span>
        </span>
        <span className="executor-activity-card__metric">
          <span className="executor-activity-card__metric-label">utilization</span>
          <span className="executor-activity-card__metric-value">
            {formatRatio(view.utilizationRatio)}
          </span>
        </span>
        <span className="executor-activity-card__metric">
          <span className="executor-activity-card__metric-label">saturation</span>
          <span className="executor-activity-card__metric-value">
            {view.saturationScore.toFixed(2)}
          </span>
        </span>
      </div>
      <div className="executor-activity-card__row executor-activity-card__row--throughput">
        <span className="executor-activity-card__metric">
          <span className="executor-activity-card__metric-label">submit</span>
          <span className="executor-activity-card__metric-value">
            {formatRate(view.submissionRate)}
          </span>
        </span>
        <span className="executor-activity-card__metric">
          <span className="executor-activity-card__metric-label">complete</span>
          <span className="executor-activity-card__metric-value">
            {formatRate(view.completionRate)}
          </span>
        </span>
        <span className="executor-activity-card__metric">
          <span className="executor-activity-card__metric-label">queue</span>
          <span className="executor-activity-card__metric-value">
            {formatSeconds(view.meanSubmissionLatencySeconds)}
          </span>
        </span>
        <span className="executor-activity-card__metric">
          <span className="executor-activity-card__metric-label">exec p95</span>
          <span className="executor-activity-card__metric-value">
            {formatSeconds(view.p95ExecutionDurationSeconds)}
          </span>
        </span>
      </div>
      {(view.backlog > 0 || view.failures > 0) && (
        <div className="executor-activity-card__badges">
          {view.backlog > 0 && (
            <span
              className="executor-activity-card__badge executor-activity-card__badge--backlog"
              data-testid="executor-activity-backlog"
            >
              {view.backlog} in queue
            </span>
          )}
          {view.failures > 0 && (
            <span
              className="executor-activity-card__badge executor-activity-card__badge--failed"
              data-testid="executor-activity-failures"
            >
              {view.failures} failed
            </span>
          )}
        </div>
      )}
    </button>
  );
}

export const ExecutorActivityCard = memo(ExecutorActivityCardImpl);
