/**
 * Pure helpers + holder for the drag-anchor state.
 *
 * A drag anchor captures the pointer's CSS x + world time + the
 * scale window at the moment the drag began. Every subsequent
 * pointer-move event uses the anchor to compute *absolute* deltas —
 * the cursor stays glued to the timeline coordinate it grabbed,
 * regardless of how many events the browser drops or coalesces.
 */

import type {
  PanDragAnchor,
} from "@/dashboard/timeline/pan/models/TimelinePanModels";

/** Pure: build a fresh anchor. */
export function makeDragAnchor(args: {
  pointerXCss: number;
  pointerTimeSeconds: number;
  timeStartSeconds: number;
  timeEndSeconds: number;
  atMs?: number;
}): PanDragAnchor {
  return {
    pointerXCss: args.pointerXCss,
    pointerTimeSeconds: args.pointerTimeSeconds,
    initialTimeStartSeconds: args.timeStartSeconds,
    initialTimeEndSeconds: args.timeEndSeconds,
    startedAtMs: args.atMs ?? nowMs(),
  };
}

/** Pure: compute the next ``timeStart`` for the supplied pointer
 *  position relative to the anchor. The anchor stays glued to the
 *  pointer in world-time space. */
export function timeStartFromAnchor(
  anchor: PanDragAnchor,
  currentPointerXCss: number,
  secondsPerPixel: number,
): number {
  const deltaPx = currentPointerXCss - anchor.pointerXCss;
  const deltaSeconds = -deltaPx * secondsPerPixel;
  return anchor.initialTimeStartSeconds + deltaSeconds;
}

/** Pure: ``true`` when the pointer has moved enough to count as a
 *  drag (vs. a click). */
export function isPastClickThreshold(
  anchor: PanDragAnchor,
  currentPointerXCss: number,
  thresholdPx: number = 3,
): boolean {
  return Math.abs(currentPointerXCss - anchor.pointerXCss) >= thresholdPx;
}

function nowMs(): number {
  return typeof performance !== "undefined" ? performance.now() : Date.now();
}
