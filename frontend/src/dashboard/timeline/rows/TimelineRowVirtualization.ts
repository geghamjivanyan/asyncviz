/**
 * Visible-row resolver — virtualization-safe culling for the row
 * renderer.
 *
 * Wraps the coordinate-system row range with three guarantees:
 *
 *   * stable row identity — every returned entry already has a stable
 *     ``rowId`` from the projection, so React keys + diagnostics remain
 *     coherent across pans,
 *   * overscan — an optional buffer of rows above + below the visible
 *     window so fast scrolling doesn't show blank space mid-frame,
 *   * deterministic ordering — entries are returned in row-index order
 *     so replay-driven frames are byte-identical to live frames.
 */

import type { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import type { TimelineRowProjectionEntry } from "@/dashboard/timeline/rows/models/TimelineRowModels";

export interface RowVisibilityOptions {
  /** Extra rows kept above + below the strict visible window. */
  overscan?: number;
}

export interface RowVisibilityResult {
  /** First row index considered visible. */
  startIndex: number;
  /** Exclusive upper bound. */
  endIndex: number;
  /** Rows in order, ready for the row renderer. */
  rows: readonly TimelineRowProjectionEntry[];
}

const EMPTY_RESULT: RowVisibilityResult = Object.freeze({
  startIndex: 0,
  endIndex: 0,
  rows: Object.freeze([]) as readonly TimelineRowProjectionEntry[],
});

/** Pure: compute visible row indices + return references — no copy
 *  beyond the slice into the projection. */
export function resolveVisibleRows(
  rows: readonly TimelineRowProjectionEntry[],
  coords: TimelineCoordinateSystem,
  options: RowVisibilityOptions = {},
): RowVisibilityResult {
  if (rows.length === 0) return EMPTY_RESULT;
  const range = coords.visibleRowRange(rows.length);
  const overscan = Math.max(0, Math.floor(options.overscan ?? 0));
  const startIndex = Math.max(0, range.startIndex - overscan);
  const endIndex = Math.min(rows.length, range.endIndex + overscan);
  if (endIndex <= startIndex) return EMPTY_RESULT;
  const visible: TimelineRowProjectionEntry[] = [];
  for (let i = startIndex; i < endIndex; i += 1) {
    const row = rows[i];
    if (row !== undefined) visible.push(row);
  }
  return { startIndex, endIndex, rows: visible };
}

/** Pure: total content height a virtualized row list would occupy. */
export function virtualContentHeight(rowCount: number, rowHeightPx: number): number {
  if (rowCount <= 0 || rowHeightPx <= 0) return 0;
  return rowCount * rowHeightPx;
}
