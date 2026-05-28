/**
 * Timeline-overlay component for executor activity markers.
 */

import { memo, useCallback } from "react";
import { cn } from "@/lib/cn";
import type { ExecutorActivityFrame } from "@/dashboard/executors/ExecutorActivityRenderer";
import { describeMarkerAnnouncement } from "@/dashboard/executors/ExecutorActivityAccessibility";

export interface ExecutorActivityOverlayProps {
  frame: ExecutorActivityFrame;
  heightPx: number;
  onActivate?: (markerId: string, executorId: string) => void;
  className?: string;
  hideWhenEmpty?: boolean;
}

interface MarkerProps {
  testId: string;
  layoutKey: string;
  severity: string;
  executorId: string;
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
  executorId,
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
      data-executor-id={executorId}
      data-severity={severity}
      onClick={handleClick}
      aria-label={ariaLabel}
      title={title}
      className="executor-activity-overlay__marker"
      style={{
        left: `${leftPx}px`,
        width: `${widthPx}px`,
        height: `${heightPx}px`,
      }}
    />
  );
};

const Marker = memo(MarkerImpl);

function ExecutorActivityOverlayImpl({
  frame,
  heightPx,
  onActivate,
  className,
  hideWhenEmpty = false,
}: ExecutorActivityOverlayProps): JSX.Element | null {
  if (hideWhenEmpty && frame.visible.length === 0 && frame.overflow === 0) {
    return null;
  }
  return (
    <div
      data-testid="executor-activity-overlay"
      data-marker-count={frame.visible.length}
      data-overflow={frame.overflow}
      className={cn("executor-activity-overlay", className)}
      style={{ height: `${heightPx}px` }}
    >
      {frame.visible.map((layout) => (
        <Marker
          key={layout.marker.id}
          testId="executor-activity-overlay-marker"
          layoutKey={layout.marker.id}
          severity={layout.marker.severity}
          executorId={layout.marker.executorId}
          ariaLabel={describeMarkerAnnouncement(layout.marker)}
          title={`${layout.marker.label}${layout.marker.detail ? ` — ${layout.marker.detail}` : ""}`}
          leftPx={layout.left}
          widthPx={layout.width}
          heightPx={heightPx}
          onActivate={
            onActivate
              ? () => onActivate(layout.marker.id, layout.marker.executorId)
              : undefined
          }
        />
      ))}
      {frame.overflow > 0 && (
        <span
          className="executor-activity-overlay__overflow"
          data-testid="executor-activity-overlay-overflow"
        >
          +{frame.overflow} more
        </span>
      )}
    </div>
  );
}

export const ExecutorActivityOverlay = memo(ExecutorActivityOverlayImpl);
