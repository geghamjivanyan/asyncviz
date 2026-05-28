/**
 * Range-selection overlay.
 *
 * Renders a translucent rectangle spanning a sequence range — used
 * for exporting a slice of the recording or for highlighting a
 * region of interest. Pure presentational; the range itself lives
 * outside the controls package (typically in the host page).
 */

import type { JSX } from "react";
import {
  sequenceToPixel,
} from "@/dashboard/replay/ReplayTimelineGeometry";
import {
  useReplayViewport,
} from "@/dashboard/replay/ReplayTimelineSelectors";

export interface ReplayTimelineSelectionProps {
  readonly startSequence: number | null;
  readonly endSequence: number | null;
  readonly heightPx?: number;
  readonly className?: string;
}

export function ReplayTimelineSelection({
  startSequence,
  endSequence,
  heightPx = 32,
  className,
}: ReplayTimelineSelectionProps): JSX.Element | null {
  const viewport = useReplayViewport();
  if (
    startSequence === null ||
    endSequence === null ||
    startSequence >= endSequence ||
    viewport.widthPx <= 0
  ) {
    return null;
  }
  const left = sequenceToPixel(startSequence, viewport);
  const right = sequenceToPixel(endSequence, viewport);
  return (
    <div
      aria-hidden
      className={
        "pointer-events-none absolute top-0 rounded bg-accent/15 " +
        (className ?? "")
      }
      style={{
        left,
        width: Math.max(2, right - left),
        height: heightPx,
      }}
    />
  );
}
