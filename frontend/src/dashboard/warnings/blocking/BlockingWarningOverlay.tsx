/**
 * Foundational timeline-overlay marker.
 *
 * The full overlay integration lands in the next task (task 6.6 wires
 * these into the timeline canvas). Today the component renders the
 * marker as a standalone SVG so it can be unit-tested + used in
 * standalone diagnostics surfaces (e.g. the diagnostics page may
 * render a small "recent freezes" overlay independently of the main
 * timeline).
 *
 * The marker carries enough information that the parent can position
 * it absolutely (``leftPercent`` / ``widthPercent``) when laid over
 * the timeline canvas.
 */

import { memo } from "react";
import type { BlockingWarningView } from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import { intentToken } from "@/dashboard/warnings/blocking/utils/formatting";

export interface BlockingWarningOverlayMarkerProps {
  view: BlockingWarningView;
  /** Position from the left of the timeline (0..100). */
  leftPercent: number;
  /** Width as a percentage (0..100). */
  widthPercent: number;
  /** Pixel height of the marker; overlay rows are typically 16-20 px. */
  heightPx?: number;
  className?: string;
  onClick?: (groupId: string) => void;
}

const INTENT_FILL: Record<ReturnType<typeof intentToken>, string> = {
  default: "fill-line",
  accent: "fill-accent",
  success: "fill-success",
  warning: "fill-warning",
  danger: "fill-danger",
};

function BlockingWarningOverlayMarkerImpl({
  view,
  leftPercent,
  widthPercent,
  heightPx = 18,
  className,
  onClick,
}: BlockingWarningOverlayMarkerProps) {
  const intent = intentToken(view.intent);
  const fill = INTENT_FILL[intent];
  return (
    <button
      type="button"
      onClick={() => onClick?.(view.groupId)}
      aria-label={`Freeze ${view.windowId ?? "no-window"}`}
      data-testid={`blocking-warning-overlay-${view.groupId}`}
      data-state={view.state}
      data-severity={view.severity}
      className={className}
      style={{
        position: "absolute",
        left: `${clamp(leftPercent, 0, 100)}%`,
        width: `${clamp(widthPercent, 0, 100)}%`,
        height: heightPx,
        padding: 0,
      }}
    >
      <svg width="100%" height={heightPx} role="presentation" aria-hidden="true">
        <rect
          x={0}
          y={2}
          width="100%"
          height={heightPx - 4}
          rx={2}
          ry={2}
          className={fill}
          opacity={view.isOpen ? 0.85 : 0.4}
        />
      </svg>
    </button>
  );
}

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, value));
}

export const BlockingWarningOverlayMarker = memo(BlockingWarningOverlayMarkerImpl);
