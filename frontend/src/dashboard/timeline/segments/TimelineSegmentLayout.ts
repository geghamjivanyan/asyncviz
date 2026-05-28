/**
 * Vertical + horizontal layout semantics for segments.
 *
 * Owns the per-row inset (so segments sit inside the row with a
 * consistent gap), the minimum visible width, and the timeline-column
 * offset (so segments draw to the right of the label gutter).
 *
 * The layout is intentionally minimal — coordinate math lives in
 * :mod:`TimelineSegmentGeometry`. Pure, no dependencies on canvas.
 */

import type { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";

export interface TimelineSegmentLayoutOptions {
  /** Vertical inset above + below segment content. */
  rowPaddingPx?: number;
  /** Minimum painted segment width (CSS px). Sub-pixel spans are
   *  widened to this so tiny segments stay visible. */
  minWidthPx?: number;
  /** Offset from the left of the canvas where the timeline column starts.
   *  Segments outside this range are clipped horizontally. */
  timelineColumnX?: number;
  /** Width of the timeline column in CSS pixels. ``undefined`` means
   *  "use viewport width minus the timeline column X". */
  timelineColumnWidthPx?: number;
}

export interface TimelineSegmentLayoutSnapshot {
  rowPaddingPx: number;
  minWidthPx: number;
  timelineColumnX: number;
  timelineColumnRightX: number;
  timelineColumnWidthPx: number;
}

const DEFAULTS: Required<TimelineSegmentLayoutOptions> = {
  rowPaddingPx: 3,
  minWidthPx: 1,
  timelineColumnX: 0,
  timelineColumnWidthPx: -1,
};

/** Canonical segment layout — instantiated per renderer. */
export class TimelineSegmentLayout {
  private readonly options: Required<TimelineSegmentLayoutOptions>;

  constructor(options: TimelineSegmentLayoutOptions = {}) {
    this.options = { ...DEFAULTS, ...options };
  }

  rowPaddingPx(): number {
    return this.options.rowPaddingPx;
  }

  minWidthPx(): number {
    return Math.max(0.5, this.options.minWidthPx);
  }

  /** Resolve the per-frame snapshot for a coordinate system. */
  resolve(coords: TimelineCoordinateSystem): TimelineSegmentLayoutSnapshot {
    const cssWidth = coords.viewport.cssWidth;
    const timelineColumnX = clampNonNegative(this.options.timelineColumnX);
    const requested = this.options.timelineColumnWidthPx;
    const timelineColumnWidthPx =
      requested >= 0 ? Math.max(0, requested) : Math.max(0, cssWidth - timelineColumnX);
    const timelineColumnRightX = timelineColumnX + timelineColumnWidthPx;
    return {
      rowPaddingPx: this.options.rowPaddingPx,
      minWidthPx: this.minWidthPx(),
      timelineColumnX,
      timelineColumnRightX,
      timelineColumnWidthPx,
    };
  }

  /** Update the timeline column boundaries — used when a row layout
   *  resolves a new label-column width at runtime. */
  setColumn(timelineColumnX: number, timelineColumnWidthPx: number): void {
    this.options.timelineColumnX = clampNonNegative(timelineColumnX);
    this.options.timelineColumnWidthPx = Math.max(0, timelineColumnWidthPx);
  }
}

function clampNonNegative(value: number): number {
  if (!Number.isFinite(value) || value < 0) return 0;
  return value;
}

export function makeSegmentLayout(
  options: TimelineSegmentLayoutOptions = {},
): TimelineSegmentLayout {
  return new TimelineSegmentLayout(options);
}
