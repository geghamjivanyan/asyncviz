/**
 * Single-semaphore summary card.
 *
 * Stateless — driven by a :type:`SemaphoreContentionView` and a select
 * callback. Severity is exposed via ``data-severity`` so the design
 * tokens (CSS variables) own the color vocabulary.
 */

import { memo, useCallback } from "react";
import { cn } from "@/lib/cn";
import type { SemaphoreContentionView } from "@/dashboard/semaphores/models/SemaphoreContentionModels";
import { describeSemaphoreForAccessibility } from "@/dashboard/semaphores/SemaphoreContentionAccessibility";
import { severityLabel } from "@/dashboard/semaphores/SemaphoreContentionSeverity";

export interface SemaphoreContentionCardProps {
  view: SemaphoreContentionView;
  selected?: boolean;
  onSelect?: (semaphoreId: string) => void;
  className?: string;
}

function formatRatio(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatSeconds(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0s";
  if (value >= 1) return `${value.toFixed(2)}s`;
  if (value >= 0.001) return `${(value * 1000).toFixed(1)}ms`;
  return `${(value * 1_000_000).toFixed(0)}µs`;
}

function SemaphoreContentionCardImpl({
  view,
  selected = false,
  onSelect,
  className,
}: SemaphoreContentionCardProps): JSX.Element {
  const handleClick = useCallback(() => {
    onSelect?.(view.semaphoreId);
  }, [view.semaphoreId, onSelect]);

  return (
    <button
      type="button"
      data-testid="semaphore-contention-card"
      data-severity={view.severity}
      data-saturated={view.saturated ? "true" : undefined}
      data-semaphore-id={view.semaphoreId}
      onClick={handleClick}
      aria-pressed={selected}
      aria-label={describeSemaphoreForAccessibility(view)}
      className={cn(
        "semaphore-contention-card",
        selected && "semaphore-contention-card--selected",
        className,
      )}
    >
      <div className="semaphore-contention-card__header">
        <span className="semaphore-contention-card__name">{view.displayName}</span>
        <span className="semaphore-contention-card__severity">
          {severityLabel(view.severity)}
        </span>
      </div>
      <div className="semaphore-contention-card__row">
        <span className="semaphore-contention-card__metric">
          <span className="semaphore-contention-card__metric-label">permits</span>
          <span className="semaphore-contention-card__metric-value">
            {view.permitsInUse}
            <span className="semaphore-contention-card__metric-divisor">
              /{view.initialValue}
            </span>
          </span>
        </span>
        <span className="semaphore-contention-card__metric">
          <span className="semaphore-contention-card__metric-label">utilization</span>
          <span className="semaphore-contention-card__metric-value">
            {formatRatio(view.utilizationRatio)}
          </span>
        </span>
        <span className="semaphore-contention-card__metric">
          <span className="semaphore-contention-card__metric-label">waiters</span>
          <span className="semaphore-contention-card__metric-value">
            {view.waiterCount}
            {view.peakWaiterCount > view.waiterCount && (
              <span className="semaphore-contention-card__metric-divisor">
                (peak {view.peakWaiterCount})
              </span>
            )}
          </span>
        </span>
      </div>
      <div className="semaphore-contention-card__row semaphore-contention-card__row--throughput">
        <span className="semaphore-contention-card__metric">
          <span className="semaphore-contention-card__metric-label">acq</span>
          <span className="semaphore-contention-card__metric-value">
            {view.acquireCount}
          </span>
        </span>
        <span className="semaphore-contention-card__metric">
          <span className="semaphore-contention-card__metric-label">rel</span>
          <span className="semaphore-contention-card__metric-value">
            {view.releaseCount}
          </span>
        </span>
        <span className="semaphore-contention-card__metric">
          <span className="semaphore-contention-card__metric-label">blocked</span>
          <span className="semaphore-contention-card__metric-value">
            {view.blockedAcquireCount}
          </span>
        </span>
        <span className="semaphore-contention-card__metric">
          <span className="semaphore-contention-card__metric-label">mean wait</span>
          <span className="semaphore-contention-card__metric-value">
            {formatSeconds(view.meanWaitSeconds)}
          </span>
        </span>
      </div>
      {(view.waiterCount > 0 || view.cancelledWaitCount > 0) && (
        <div className="semaphore-contention-card__badges">
          {view.waiterCount > 0 && (
            <span
              className="semaphore-contention-card__badge semaphore-contention-card__badge--waiter"
              data-testid="semaphore-contention-waiters"
            >
              {view.waiterCount} waiter
              {view.waiterCount === 1 ? "" : "s"}
            </span>
          )}
          {view.cancelledWaitCount > 0 && (
            <span
              className="semaphore-contention-card__badge semaphore-contention-card__badge--cancelled"
              data-testid="semaphore-contention-cancelled"
            >
              {view.cancelledWaitCount} cancelled wait
              {view.cancelledWaitCount === 1 ? "" : "s"}
            </span>
          )}
        </div>
      )}
    </button>
  );
}

export const SemaphoreContentionCard = memo(SemaphoreContentionCardImpl);
