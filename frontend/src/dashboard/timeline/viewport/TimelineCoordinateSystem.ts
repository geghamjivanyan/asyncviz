/**
 * World ↔ screen coordinate system.
 *
 * One :class:`TimelineCoordinateSystem` is computed per frame from a
 * :type:`TimelineCamera` + :type:`TimelineViewport`. Drawing code +
 * hit testing both reference this object — there's exactly one place
 * that owns the math.
 *
 * The implementation is pure (no canvas dependency) so it's testable
 * without jsdom and reusable on a worker thread.
 */

import type { TimelineCamera } from "@/dashboard/timeline/viewport/TimelineCamera";
import type { TimelineViewport } from "@/dashboard/timeline/viewport/TimelineViewport";

export interface VisibleRowRange {
  /** First fully or partially visible row index. */
  startIndex: number;
  /** Exclusive end — one past the last visible row. */
  endIndex: number;
}

export interface VisibleSegmentSpan {
  /** Left X in CSS pixels. */
  x0: number;
  /** Right X in CSS pixels. */
  x1: number;
  /** Pixel width (always > 0; clamped to a sub-pixel minimum). */
  width: number;
}

const MIN_SEGMENT_WIDTH_PX = 0.5;

export class TimelineCoordinateSystem {
  readonly camera: TimelineCamera;
  readonly viewport: TimelineViewport;
  /** Pre-computed pixels per world second. */
  readonly pixelsPerSecond: number;

  constructor(camera: TimelineCamera, viewport: TimelineViewport) {
    this.camera = camera;
    this.viewport = viewport;
    const duration = camera.timeEnd - camera.timeStart;
    this.pixelsPerSecond = duration > 0 ? viewport.cssWidth / duration : 0;
  }

  /** Map a world-time value to its X coordinate in CSS pixels. */
  timeToX(seconds: number): number {
    return (seconds - this.camera.timeStart) * this.pixelsPerSecond;
  }

  /** Map an X coordinate (CSS pixels) back to world seconds. */
  xToTime(x: number): number {
    if (this.pixelsPerSecond === 0) return this.camera.timeStart;
    return this.camera.timeStart + x / this.pixelsPerSecond;
  }

  /** Map a row index to its top-edge Y coordinate in CSS pixels. */
  rowToY(rowIndex: number): number {
    return (rowIndex - this.camera.rowStart) * this.camera.rowHeight;
  }

  /** Map an X,Y pixel pair back to (row, time). Returns ``null`` for
   *  pixels outside the canvas viewport. */
  pointToWorld(xCss: number, yCss: number): { time: number; rowIndex: number } | null {
    if (xCss < 0 || yCss < 0 || xCss > this.viewport.cssWidth || yCss > this.viewport.cssHeight) {
      return null;
    }
    return {
      time: this.xToTime(xCss),
      rowIndex: this.yToRow(yCss),
    };
  }

  /** Map a Y coordinate to a (possibly fractional) row index. */
  yToRow(y: number): number {
    return this.camera.rowStart + y / this.camera.rowHeight;
  }

  /** Compute the visible row index range (clipped to ``totalRows``). */
  visibleRowRange(totalRows: number): VisibleRowRange {
    const rowHeight = this.camera.rowHeight;
    const startIndex = Math.max(0, Math.floor(this.camera.rowStart));
    const visibleCount = Math.ceil(this.viewport.cssHeight / rowHeight) + 1;
    const endIndex = Math.min(totalRows, startIndex + visibleCount);
    return { startIndex, endIndex };
  }

  /** Compute the screen span (and clip-test) of a segment defined by
   *  ``[startSeconds, endSeconds]``. Returns ``null`` when the segment
   *  is entirely outside the viewport. */
  segmentSpan(startSeconds: number, endSeconds: number): VisibleSegmentSpan | null {
    if (endSeconds < this.camera.timeStart) return null;
    if (startSeconds > this.camera.timeEnd) return null;
    const x0 = Math.max(0, this.timeToX(startSeconds));
    const x1 = Math.min(this.viewport.cssWidth, this.timeToX(endSeconds));
    const width = Math.max(MIN_SEGMENT_WIDTH_PX, x1 - x0);
    return { x0, x1, width };
  }

  /** Quick cull test — ``true`` when [startSeconds, endSeconds] overlaps
   *  the visible window. */
  intersectsTime(startSeconds: number, endSeconds: number): boolean {
    return endSeconds >= this.camera.timeStart && startSeconds <= this.camera.timeEnd;
  }

  /** ``true`` when a row is currently on-screen. */
  intersectsRow(rowIndex: number): boolean {
    const y = this.rowToY(rowIndex);
    return y + this.camera.rowHeight >= 0 && y <= this.viewport.cssHeight;
  }
}

/** Pure constructor — useful in tests that compose the system without
 *  going through React. */
export function makeCoordinateSystem(
  camera: TimelineCamera,
  viewport: TimelineViewport,
): TimelineCoordinateSystem {
  return new TimelineCoordinateSystem(camera, viewport);
}
