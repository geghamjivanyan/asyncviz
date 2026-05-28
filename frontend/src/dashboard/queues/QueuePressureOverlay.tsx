/**
 * Timeline-overlay component for queue pressure markers.
 *
 * Stateless — driven by a :func:`layoutFrame` result. The container
 * computes the viewport math + the frame; this component just renders
 * the buttons. Each marker is a real focusable button so keyboard
 * users can step through them with Tab.
 */

import { memo, useCallback } from "react";
import { cn } from "@/lib/cn";
import type { QueuePressureFrame } from "@/dashboard/queues/QueuePressureRenderer";
import { describeMarkerAnnouncement } from "@/dashboard/queues/QueuePressureAccessibility";

export interface QueuePressureOverlayProps {
  /** Result of :func:`layoutFrame`. */
  frame: QueuePressureFrame;
  /** Container height in CSS pixels — the markers stretch to fill. */
  heightPx: number;
  /** Called when a marker is activated (click or Enter/Space). */
  onActivate?: (markerId: string, queueId: string) => void;
  className?: string;
  /** Skip rendering when there are no visible markers. */
  hideWhenEmpty?: boolean;
}

interface MarkerProps {
  testId: string;
  layoutKey: string;
  severity: string;
  queueId: string;
  ariaLabel: string;
  title: string;
  leftPx: number;
  widthPx: number;
  heightPx: number;
  onActivate?: () => void;
}

const MarkerImpl = ({
  testId,
  layoutKey,
  severity,
  queueId,
  ariaLabel,
  title,
  leftPx,
  widthPx,
  heightPx,
  onActivate,
}: MarkerProps): JSX.Element => {
  const handleClick = useCallback(() => onActivate?.(), [onActivate]);
  return (
    <button
      type="button"
      data-testid={testId}
      data-marker-id={layoutKey}
      data-queue-id={queueId}
      data-severity={severity}
      onClick={handleClick}
      aria-label={ariaLabel}
      title={title}
      className="queue-pressure-overlay__marker"
      style={{
        left: `${leftPx}px`,
        width: `${widthPx}px`,
        height: `${heightPx}px`,
      }}
    />
  );
};

const Marker = memo(MarkerImpl);

function QueuePressureOverlayImpl({
  frame,
  heightPx,
  onActivate,
  className,
  hideWhenEmpty = false,
}: QueuePressureOverlayProps): JSX.Element | null {
  if (hideWhenEmpty && frame.visible.length === 0 && frame.overflow === 0) {
    return null;
  }
  return (
    <div
      data-testid="queue-pressure-overlay"
      data-marker-count={frame.visible.length}
      data-overflow={frame.overflow}
      className={cn("queue-pressure-overlay", className)}
      style={{ height: `${heightPx}px` }}
    >
      {frame.visible.map((layout) => (
        <Marker
          key={layout.marker.id}
          testId="queue-pressure-overlay-marker"
          layoutKey={layout.marker.id}
          severity={layout.marker.severity}
          queueId={layout.marker.queueId}
          ariaLabel={describeMarkerAnnouncement(layout.marker)}
          title={`${layout.marker.label}${layout.marker.detail ? ` — ${layout.marker.detail}` : ""}`}
          leftPx={layout.left}
          widthPx={layout.width}
          heightPx={heightPx}
          onActivate={
            onActivate
              ? () => onActivate(layout.marker.id, layout.marker.queueId)
              : undefined
          }
        />
      ))}
      {frame.overflow > 0 && (
        <span
          className="queue-pressure-overlay__overflow"
          data-testid="queue-pressure-overlay-overflow"
        >
          +{frame.overflow} more
        </span>
      )}
    </div>
  );
}

export const QueuePressureOverlay = memo(QueuePressureOverlayImpl);
