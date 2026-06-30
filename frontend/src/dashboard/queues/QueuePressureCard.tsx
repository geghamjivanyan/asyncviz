/**
 * Single-queue summary card.
 *
 * Stateless — driven by a :type:`QueuePressureView` and a select
 * callback. Reads the severity class from a ``data-severity``
 * attribute so the design tokens (CSS variables) own the color
 * vocabulary.
 */

import { memo, useCallback } from "react";
import { cn } from "@/lib/cn";
import type { QueuePressureView } from "@/dashboard/queues/models/QueuePressureModels";
import { describeQueueForAccessibility } from "@/dashboard/queues/QueuePressureAccessibility";
import { severityLabel } from "@/dashboard/queues/QueuePressureSeverity";

export interface QueuePressureCardProps {
  view: QueuePressureView;
  selected?: boolean;
  onSelect?: (queueId: string) => void;
  className?: string;
}

function formatRate(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0/s";
  if (value >= 100) return `${value.toFixed(0)}/s`;
  if (value >= 10) return `${value.toFixed(1)}/s`;
  return `${value.toFixed(2)}/s`;
}

function formatRatio(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function QueuePressureCardImpl({
  view,
  selected = false,
  onSelect,
  className,
}: QueuePressureCardProps): JSX.Element {
  const handleClick = useCallback(() => {
    onSelect?.(view.queueId);
  }, [view.queueId, onSelect]);

  return (
    <button
      type="button"
      data-testid="queue-pressure-card"
      data-severity={view.severity}
      data-saturated={view.saturated ? "true" : undefined}
      data-queue-id={view.queueId}
      onClick={handleClick}
      aria-pressed={selected}
      aria-label={describeQueueForAccessibility(view)}
      className={cn("queue-pressure-card", selected && "queue-pressure-card--selected", className)}
    >
      <div className="queue-pressure-card__header">
        <span className="queue-pressure-card__name">{view.displayName}</span>
        <span className="queue-pressure-card__severity">{severityLabel(view.severity)}</span>
      </div>
      <div className="queue-pressure-card__row">
        <span className="queue-pressure-card__metric">
          <span className="queue-pressure-card__metric-label">size</span>
          <span className="queue-pressure-card__metric-value">
            {view.currentSize}
            {view.maxsize > 0 && (
              <span className="queue-pressure-card__metric-divisor">/{view.maxsize}</span>
            )}
          </span>
        </span>
        <span className="queue-pressure-card__metric">
          <span className="queue-pressure-card__metric-label">occupancy</span>
          <span className="queue-pressure-card__metric-value">
            {formatRatio(view.occupancyRatio)}
          </span>
        </span>
        <span className="queue-pressure-card__metric">
          <span className="queue-pressure-card__metric-label">pressure</span>
          <span className="queue-pressure-card__metric-value">{view.pressureScore.toFixed(2)}</span>
        </span>
      </div>
      <div className="queue-pressure-card__row queue-pressure-card__row--throughput">
        <span className="queue-pressure-card__metric">
          <span className="queue-pressure-card__metric-label">put</span>
          <span className="queue-pressure-card__metric-value">{formatRate(view.putRate)}</span>
        </span>
        <span className="queue-pressure-card__metric">
          <span className="queue-pressure-card__metric-label">get</span>
          <span className="queue-pressure-card__metric-value">{formatRate(view.getRate)}</span>
        </span>
        <span className="queue-pressure-card__metric">
          <span className="queue-pressure-card__metric-label">Δ p−c</span>
          <span className="queue-pressure-card__metric-value">{view.producerConsumerDelta}</span>
        </span>
      </div>
      {(view.blockedProducers > 0 || view.blockedConsumers > 0) && (
        <div className="queue-pressure-card__badges">
          {view.blockedProducers > 0 && (
            <span
              className="queue-pressure-card__badge queue-pressure-card__badge--producer"
              data-testid="queue-pressure-blocked-producers"
            >
              {view.blockedProducers} blocked producer
              {view.blockedProducers === 1 ? "" : "s"}
            </span>
          )}
          {view.blockedConsumers > 0 && (
            <span
              className="queue-pressure-card__badge queue-pressure-card__badge--consumer"
              data-testid="queue-pressure-blocked-consumers"
            >
              {view.blockedConsumers} blocked consumer
              {view.blockedConsumers === 1 ? "" : "s"}
            </span>
          )}
        </div>
      )}
    </button>
  );
}

export const QueuePressureCard = memo(QueuePressureCardImpl);
