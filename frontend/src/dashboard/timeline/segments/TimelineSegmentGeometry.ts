/**
 * Pure world → screen geometry for segments.
 *
 * Resolves the (x, y, width, height) of a single segment in CSS
 * pixels. Centralises:
 *
 *   * world-time → screen X projection,
 *   * row index → screen Y projection,
 *   * minimum visible width enforcement,
 *   * timeline-column clipping (so segments cannot leak into the
 *     label column),
 *   * active-segment extension to the camera's right edge.
 *
 * The module is dependency-free apart from the coordinate system,
 * so it runs on a worker thread later. Tests drive it directly.
 */

import type { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import type { TimelineRenderSegment } from "@/dashboard/timeline/rendering/TimelineLayer";
import type { TimelineSegmentLayoutSnapshot } from "@/dashboard/timeline/segments/TimelineSegmentLayout";

/** Screen-space rectangle for a single segment. */
export interface SegmentScreenRect {
  x: number;
  y: number;
  width: number;
  height: number;
  /** ``true`` when the segment was clipped on the left edge. */
  clippedLeft: boolean;
  /** ``true`` when the segment was clipped on the right edge. */
  clippedRight: boolean;
  /** Pixels per second at the time the rect was computed — useful
   *  when downstream code needs to back-derive sub-pixel detail. */
  pixelsPerSecond: number;
}

/** Pure: project a single segment into screen-space. Returns ``null``
 *  when the segment is entirely outside the timeline column. */
export function projectSegmentRect(args: {
  segment: TimelineRenderSegment;
  coords: TimelineCoordinateSystem;
  layout: TimelineSegmentLayoutSnapshot;
}): SegmentScreenRect | null {
  const { segment, coords, layout } = args;
  const { rowPaddingPx, minWidthPx, timelineColumnX, timelineColumnRightX } = layout;

  // Resolve the segment's effective end. Active segments are rendered
  // to the right edge of the camera so they extend live.
  const startSeconds = segment.startSeconds;
  const endSeconds = segment.isActive
    ? Math.max(coords.camera.timeEnd, segment.endSeconds)
    : segment.endSeconds;

  if (endSeconds < coords.camera.timeStart) return null;
  if (startSeconds > coords.camera.timeEnd) return null;

  // World → CSS-pixel projection relative to the timeline column. The
  // coordinate system's ``pixelsPerSecond`` is viewport-wide, so we
  // re-scale using the timeline column width when it differs from the
  // viewport width.
  const cameraDuration = Math.max(Number.EPSILON, coords.camera.timeEnd - coords.camera.timeStart);
  const columnPixelsPerSecond =
    layout.timelineColumnWidthPx > 0 ? layout.timelineColumnWidthPx / cameraDuration : 0;
  const rawX0 = timelineColumnX + (startSeconds - coords.camera.timeStart) * columnPixelsPerSecond;
  const rawX1 = timelineColumnX + (endSeconds - coords.camera.timeStart) * columnPixelsPerSecond;

  let x0 = rawX0;
  let x1 = rawX1;
  let clippedLeft = false;
  let clippedRight = false;

  if (x0 < timelineColumnX) {
    x0 = timelineColumnX;
    clippedLeft = true;
  }
  if (x1 > timelineColumnRightX) {
    x1 = timelineColumnRightX;
    clippedRight = true;
  }
  if (x1 <= timelineColumnX || x0 >= timelineColumnRightX) {
    return null;
  }
  const width = Math.max(minWidthPx, x1 - x0);

  const rowTopY = coords.rowToY(segment.rowIndex);
  const rowHeight = coords.camera.rowHeight;
  if (rowTopY + rowHeight < 0) return null;
  if (rowTopY > coords.viewport.cssHeight) return null;
  const innerHeight = Math.max(1, rowHeight - rowPaddingPx * 2);
  const y = rowTopY + rowPaddingPx;

  return {
    x: x0,
    y,
    width,
    height: innerHeight,
    clippedLeft,
    clippedRight,
    pixelsPerSecond: columnPixelsPerSecond,
  };
}

/** Pure: snap a pair of pixel coords to half-pixel offsets so strokes
 *  render crisp on integer device-pixel grids. */
export function crispStrokeRect(rect: SegmentScreenRect): {
  x: number;
  y: number;
  width: number;
  height: number;
} {
  const x = Math.round(rect.x) + 0.5;
  const y = Math.round(rect.y) + 0.5;
  const width = Math.max(0, Math.round(rect.width) - 1);
  const height = Math.max(0, Math.round(rect.height) - 1);
  return { x, y, width, height };
}
