/**
 * Pure hit testing for lifecycle segments.
 *
 * Translates a CSS-pixel pointer position into the segment underneath
 * it. The implementation is overlap-safe: when multiple segments
 * cover the pointer, the one with the *latest* start time wins —
 * that matches the visual painting order (later segments draw over
 * earlier ones).
 *
 * The module is pure (no canvas), runs in workers, and powers
 * tooltips, click-to-focus, and future scrubbing tools.
 */

import type { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import type { TimelineSegmentProjectionEntry } from "@/dashboard/timeline/segments/models/TimelineSegmentModels";
import type { TimelineSegmentLayoutSnapshot } from "@/dashboard/timeline/segments/TimelineSegmentLayout";
import type { TimelineSegmentMetrics } from "@/dashboard/timeline/segments/TimelineSegmentMetrics";

export interface SegmentHitTestArgs {
  xCss: number;
  yCss: number;
  coords: TimelineCoordinateSystem;
  layout: TimelineSegmentLayoutSnapshot;
  entries: readonly TimelineSegmentProjectionEntry[];
  metrics?: TimelineSegmentMetrics;
}

export interface SegmentHitTestResult {
  segment: TimelineSegmentProjectionEntry | null;
  /** World time at the pointer (inside the timeline column) — ``null``
   *  when the pointer is outside the timeline column. */
  timeSeconds: number | null;
  /** Row index under the pointer — fractional rows allowed. */
  rowIndexFractional: number;
}

/** Pure: locate the topmost segment under the pointer. */
export function hitTestSegment(args: SegmentHitTestArgs): SegmentHitTestResult {
  const { xCss, yCss, coords, layout, entries, metrics } = args;
  metrics?.recordHitTest();

  const rowIndexFractional = coords.yToRow(yCss);
  const rowIndex = Math.floor(rowIndexFractional);

  if (xCss < layout.timelineColumnX || xCss > layout.timelineColumnRightX) {
    return { segment: null, timeSeconds: null, rowIndexFractional };
  }
  if (rowIndex < 0) {
    return { segment: null, timeSeconds: pointerTime(coords, layout, xCss), rowIndexFractional };
  }
  const timeSeconds = pointerTime(coords, layout, xCss);

  let best: TimelineSegmentProjectionEntry | null = null;
  for (const entry of entries) {
    if (entry.rowIndex !== rowIndex) continue;
    const start = entry.startSeconds;
    const end = entry.isActive
      ? Math.max(coords.camera.timeEnd, entry.endSeconds)
      : entry.endSeconds;
    if (timeSeconds < start || timeSeconds > end) continue;
    if (best === null || entry.startSeconds > best.startSeconds) best = entry;
  }
  return { segment: best, timeSeconds, rowIndexFractional };
}

function pointerTime(
  coords: TimelineCoordinateSystem,
  layout: TimelineSegmentLayoutSnapshot,
  xCss: number,
): number {
  if (layout.timelineColumnWidthPx <= 0) return coords.camera.timeStart;
  const duration = Math.max(Number.EPSILON, coords.camera.timeEnd - coords.camera.timeStart);
  const columnPixelsPerSecond = layout.timelineColumnWidthPx / duration;
  if (columnPixelsPerSecond <= 0) return coords.camera.timeStart;
  const localX = xCss - layout.timelineColumnX;
  return coords.camera.timeStart + localX / columnPixelsPerSecond;
}
