/**
 * Pure visible-segment culling helpers.
 *
 * The segment renderer culls in two passes:
 *
 *   1. visible-row range — anything outside the camera's row window
 *      is dropped without computing its rect,
 *   2. visible-time intersection — segments whose ``[start, end]``
 *      range falls outside the camera time window are dropped.
 *
 * Both passes are pure so the renderer can call them every frame
 * without allocating intermediate sets.
 */

import type { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import type { TimelineSegmentProjectionEntry } from "@/dashboard/timeline/segments/models/TimelineSegmentModels";

export interface SegmentVisibilityOptions {
  /** Extra rows kept above + below the strict visible window. */
  rowOverscan?: number;
  /** Extra seconds kept on each side of the visible time window. */
  timeOverscanSeconds?: number;
}

export interface SegmentVisibilityResult {
  /** First row index considered visible. */
  rowStartIndex: number;
  /** Exclusive upper bound for visible rows. */
  rowEndIndex: number;
  /** Entries inside the visible window, in deterministic order. */
  entries: readonly TimelineSegmentProjectionEntry[];
}

const EMPTY_RESULT: SegmentVisibilityResult = Object.freeze({
  rowStartIndex: 0,
  rowEndIndex: 0,
  entries: Object.freeze([]) as readonly TimelineSegmentProjectionEntry[],
});

/** Pure: cull a projection down to entries the camera can see. */
export function resolveVisibleSegments(
  entries: readonly TimelineSegmentProjectionEntry[],
  coords: TimelineCoordinateSystem,
  totalRows: number,
  options: SegmentVisibilityOptions = {},
): SegmentVisibilityResult {
  if (entries.length === 0) return EMPTY_RESULT;
  const rowOverscan = Math.max(0, Math.floor(options.rowOverscan ?? 0));
  const timeOverscan = Math.max(0, options.timeOverscanSeconds ?? 0);
  const range = coords.visibleRowRange(totalRows);
  const rowStartIndex = Math.max(0, range.startIndex - rowOverscan);
  const rowEndIndex = Math.min(totalRows, range.endIndex + rowOverscan);
  const timeStart = coords.camera.timeStart - timeOverscan;
  const timeEnd = coords.camera.timeEnd + timeOverscan;

  const out: TimelineSegmentProjectionEntry[] = [];
  for (const entry of entries) {
    if (entry.rowIndex < rowStartIndex || entry.rowIndex >= rowEndIndex) continue;
    const effectiveEnd = entry.isActive
      ? Math.max(coords.camera.timeEnd, entry.endSeconds)
      : entry.endSeconds;
    if (effectiveEnd < timeStart) continue;
    if (entry.startSeconds > timeEnd) continue;
    out.push(entry);
  }
  return { rowStartIndex, rowEndIndex, entries: out };
}

/** Pure: ``true`` when two segment intervals overlap on the same row. */
export function segmentsOverlap(
  a: TimelineSegmentProjectionEntry,
  b: TimelineSegmentProjectionEntry,
): boolean {
  if (a.rowIndex !== b.rowIndex) return false;
  return a.startSeconds < b.endSeconds && b.startSeconds < a.endSeconds;
}
