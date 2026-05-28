/**
 * Visible-row + visible-segment culling helpers.
 *
 * Pure functions — the renderer calls these once per frame to decide
 * what to draw. Tests drive them directly.
 */

import type { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";

export interface CullableRow {
  /** Row index in the global row ordering. */
  rowIndex: number;
}

export interface CullableSegment {
  /** Row this segment belongs to. */
  rowIndex: number;
  /** Start time in world seconds. */
  startSeconds: number;
  /** End time in world seconds. */
  endSeconds: number;
}

/** Pure: keep only rows currently on-screen. */
export function cullRows<T extends CullableRow>(
  rows: readonly T[],
  coords: TimelineCoordinateSystem,
): T[] {
  const range = coords.visibleRowRange(rows.length);
  const out: T[] = [];
  for (let i = range.startIndex; i < range.endIndex; i += 1) {
    const row = rows[i];
    if (row !== undefined) out.push(row);
  }
  return out;
}

/** Pure: keep only segments whose row is on-screen *and* whose time
 *  range intersects the visible window. */
export function cullSegments<T extends CullableSegment>(
  segments: readonly T[],
  coords: TimelineCoordinateSystem,
  totalRows: number,
): T[] {
  const range = coords.visibleRowRange(totalRows);
  const out: T[] = [];
  for (const seg of segments) {
    if (seg.rowIndex < range.startIndex || seg.rowIndex >= range.endIndex) continue;
    if (!coords.intersectsTime(seg.startSeconds, seg.endSeconds)) continue;
    out.push(seg);
  }
  return out;
}
