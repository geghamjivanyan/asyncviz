/**
 * Timeline-overlay component for semaphore contention markers.
 *
 * Stateless — driven by a :func:`layoutFrame` result. Each marker is
 * a focusable button so keyboard users can step through them with Tab.
 */

import { memo, useCallback } from "react";
import { cn } from "@/lib/cn";
import type { SemaphoreContentionFrame } from "@/dashboard/semaphores/SemaphoreContentionRenderer";
import { describeMarkerAnnouncement } from "@/dashboard/semaphores/SemaphoreContentionAccessibility";

export interface SemaphoreContentionOverlayProps {
  frame: SemaphoreContentionFrame;
  heightPx: number;
  onActivate?: (markerId: string, semaphoreId: string) => void;
  className?: string;
  hideWhenEmpty?: boolean;
}

interface MarkerProps {
  testId: string;
  layoutKey: string;
  severity: string;
  semaphoreId: string;
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
  semaphoreId,
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
      data-semaphore-id={semaphoreId}
      data-severity={severity}
      onClick={handleClick}
      aria-label={ariaLabel}
      title={title}
      className="semaphore-contention-overlay__marker"
      style={{
        left: `${leftPx}px`,
        width: `${widthPx}px`,
        height: `${heightPx}px`,
      }}
    />
  );
};

const Marker = memo(MarkerImpl);

function SemaphoreContentionOverlayImpl({
  frame,
  heightPx,
  onActivate,
  className,
  hideWhenEmpty = false,
}: SemaphoreContentionOverlayProps): JSX.Element | null {
  if (hideWhenEmpty && frame.visible.length === 0 && frame.overflow === 0) {
    return null;
  }
  return (
    <div
      data-testid="semaphore-contention-overlay"
      data-marker-count={frame.visible.length}
      data-overflow={frame.overflow}
      className={cn("semaphore-contention-overlay", className)}
      style={{ height: `${heightPx}px` }}
    >
      {frame.visible.map((layout) => (
        <Marker
          key={layout.marker.id}
          testId="semaphore-contention-overlay-marker"
          layoutKey={layout.marker.id}
          severity={layout.marker.severity}
          semaphoreId={layout.marker.semaphoreId}
          ariaLabel={describeMarkerAnnouncement(layout.marker)}
          title={`${layout.marker.label}${layout.marker.detail ? ` — ${layout.marker.detail}` : ""}`}
          leftPx={layout.left}
          widthPx={layout.width}
          heightPx={heightPx}
          onActivate={
            onActivate
              ? () => onActivate(layout.marker.id, layout.marker.semaphoreId)
              : undefined
          }
        />
      ))}
      {frame.overflow > 0 && (
        <span
          className="semaphore-contention-overlay__overflow"
          data-testid="semaphore-contention-overlay-overflow"
        >
          +{frame.overflow} more
        </span>
      )}
    </div>
  );
}

export const SemaphoreContentionOverlay = memo(SemaphoreContentionOverlayImpl);
