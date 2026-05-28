/**
 * Pure visibility-culling helpers used by the virtualization engine.
 *
 * Two specialized helpers:
 *
 *   * :func:`cullRowsByWindow` — slices a stable rows array by the
 *     row-window indices,
 *   * :func:`cullSegmentsByWindow` — falls back to a linear scan when
 *     no spatial index is supplied, or uses the index when one is.
 *
 * Both helpers are pure so the engine can keep them in a single
 * hot-path call without owning any state.
 */

import type {
  SpatialIndexable,
  TimelineSegmentSpatialIndex,
} from "@/dashboard/timeline/virtualization/utils/spatialIndex";
import type {
  TimelineRowWindow,
  TimelineTimeWindow,
} from "@/dashboard/timeline/virtualization/models/TimelineVirtualizationModels";

export interface CullableRow {
  rowIndex: number;
}

/** Pure: slice ``rows`` by ``[overscanStartIndex, overscanEndIndex)``. */
export function cullRowsByWindow<T extends CullableRow>(
  rows: readonly T[],
  window: TimelineRowWindow,
): T[] {
  if (rows.length === 0) return [];
  const start = Math.max(0, window.overscanStartIndex);
  const end = Math.min(rows.length, window.overscanEndIndex);
  if (end <= start) return [];
  const out: T[] = [];
  for (let i = start; i < end; i += 1) {
    const row = rows[i];
    if (row !== undefined) out.push(row);
  }
  return out;
}

export interface CullSegmentsLinearArgs<TSegment extends SpatialIndexable> {
  segments: readonly TSegment[];
  rowWindow: TimelineRowWindow;
  timeWindow: TimelineTimeWindow;
}

/** Pure: linear-scan segment culling — used as a fallback when no
 *  spatial index is available. */
export function cullSegmentsLinear<TSegment extends SpatialIndexable>(
  args: CullSegmentsLinearArgs<TSegment>,
): TSegment[] {
  const { segments, rowWindow, timeWindow } = args;
  if (segments.length === 0) return [];
  const out: TSegment[] = [];
  for (const seg of segments) {
    if (seg.rowIndex < rowWindow.overscanStartIndex || seg.rowIndex >= rowWindow.overscanEndIndex) {
      continue;
    }
    const effectiveEnd =
      seg.isActive === true
        ? Math.max(seg.endSeconds, timeWindow.endSeconds)
        : seg.endSeconds;
    if (effectiveEnd < timeWindow.overscanStartSeconds) continue;
    if (seg.startSeconds > timeWindow.overscanEndSeconds) continue;
    out.push(seg);
  }
  return out;
}

export interface CullSegmentsIndexedArgs<TSegment extends SpatialIndexable> {
  index: TimelineSegmentSpatialIndex<TSegment>;
  rowWindow: TimelineRowWindow;
  timeWindow: TimelineTimeWindow;
}

/** Pure: spatial-index segment culling. */
export function cullSegmentsIndexed<TSegment extends SpatialIndexable>(
  args: CullSegmentsIndexedArgs<TSegment>,
): TSegment[] {
  const { index, rowWindow, timeWindow } = args;
  return index.query({
    startRowIndex: rowWindow.overscanStartIndex,
    endRowIndex: rowWindow.overscanEndIndex,
    startSeconds: timeWindow.overscanStartSeconds,
    endSeconds: timeWindow.overscanEndSeconds,
    cameraEndSeconds: timeWindow.endSeconds,
  });
}
