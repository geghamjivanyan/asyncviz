/**
 * Pure helpers for resolving a :type:`ZoomAnchor` to a world-time
 * pivot.
 *
 * The controller resolves anchors against the current scale snapshot
 * — every zoom operation routes through here so the cursor-stable
 * invariant is guaranteed at exactly one site.
 */

import type { TimelineTimeScale } from "@/dashboard/timeline/scaling/TimelineTimeScale";
import type { ZoomAnchor } from "@/dashboard/timeline/zoom/models/TimelineZoomModels";

export interface AnchorResolveContext {
  scale: TimelineTimeScale;
  /** Most recent cursor world-time the controller observed — used
   *  when ``anchor.kind === "cursor"``. ``null`` falls back to the
   *  viewport center. */
  cursorTimeSeconds?: number | null;
}

/** Pure: resolve any :type:`ZoomAnchor` to a single world-time pivot. */
export function resolveAnchorTime(
  anchor: ZoomAnchor,
  context: AnchorResolveContext,
): number {
  const { scale, cursorTimeSeconds } = context;
  switch (anchor.kind) {
    case "time":
      if (anchor.timeSeconds !== undefined && Number.isFinite(anchor.timeSeconds)) {
        return anchor.timeSeconds;
      }
      return centerTime(scale);
    case "x":
      if (anchor.xCss !== undefined && Number.isFinite(anchor.xCss)) {
        return scale.xToTime(anchor.xCss);
      }
      return centerTime(scale);
    case "cursor":
      if (cursorTimeSeconds !== null && cursorTimeSeconds !== undefined) {
        return cursorTimeSeconds;
      }
      return centerTime(scale);
    case "center":
    default:
      return centerTime(scale);
  }
}

function centerTime(scale: TimelineTimeScale): number {
  return scale.timeStart + scale.durationSeconds / 2;
}

/** Convenience constructor — keep anchor object literals readable. */
export function timeAnchor(timeSeconds: number): ZoomAnchor {
  return { kind: "time", timeSeconds };
}

export function xAnchor(xCss: number): ZoomAnchor {
  return { kind: "x", xCss };
}

export function cursorAnchor(): ZoomAnchor {
  return { kind: "cursor" };
}

export function centerAnchor(): ZoomAnchor {
  return { kind: "center" };
}
