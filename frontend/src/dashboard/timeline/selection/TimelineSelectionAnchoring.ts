/**
 * Helpers that build :type:`SelectionAnchor` values from raw pointer
 * hits. Keeping the construction here means the controller's pointer
 * path stays focused on the selection mutation, not anchor
 * bookkeeping.
 */

import type { SelectionAnchor } from "@/dashboard/timeline/selection/models/TimelineSelectionModels";

export function anchorFromHit(args: {
  timeSeconds?: number | null;
  segmentId?: string | null;
}): SelectionAnchor {
  return {
    timeSeconds: typeof args.timeSeconds === "number" ? args.timeSeconds : null,
    segmentId: args.segmentId ?? null,
  };
}

export function anchorFromTime(timeSeconds: number): SelectionAnchor {
  return { timeSeconds, segmentId: null };
}

export function anchorFromSegment(segmentId: string, timeSeconds?: number): SelectionAnchor {
  return { timeSeconds: timeSeconds ?? null, segmentId };
}

/** Pure: ``true`` when two anchors describe the same intent. */
export function anchorsEqual(a: SelectionAnchor, b: SelectionAnchor): boolean {
  return a.timeSeconds === b.timeSeconds && a.segmentId === b.segmentId;
}
