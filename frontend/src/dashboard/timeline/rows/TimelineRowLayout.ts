/**
 * Pure row-layout semantics.
 *
 * The layout owns the spatial decisions every other row layer reads:
 *
 *   * how tall a row is,
 *   * how much vertical padding sits inside a row,
 *   * where the label column ends and the timeline column starts,
 *   * how lineage indentation expands inside the label column.
 *
 * The layout is intentionally framework-free + dependency-free so it
 * runs on a worker thread later. It returns frozen objects per
 * resolution so callers can hold references without worrying about
 * mutation.
 */

import type { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";

export interface TimelineRowLayoutOptions {
  /** Single-row height in CSS pixels — overrides camera default when set. */
  rowHeightPx?: number;
  /** Inset applied above + below the row content. */
  rowPaddingPx?: number;
  /** Width of the label column in CSS pixels. */
  labelColumnWidthPx?: number;
  /** Min label-column width when shrunk for narrow viewports. */
  minLabelColumnWidthPx?: number;
  /** Max label-column width when expanded for wide viewports. */
  maxLabelColumnWidthPx?: number;
  /** Indentation per lineage depth level (CSS pixels). */
  indentPerDepthPx?: number;
  /** Maximum indentation cap (CSS pixels). */
  maxIndentPx?: number;
  /** Gutter between label column and timeline column (CSS pixels). */
  columnGutterPx?: number;
}

/** Resolved per-frame layout — pure data, safe to memoize. */
export interface TimelineRowLayoutSnapshot {
  rowHeightPx: number;
  rowPaddingPx: number;
  /** Final label-column width after viewport clamping. */
  labelColumnWidthPx: number;
  /** X coordinate where the timeline column starts. */
  timelineColumnX: number;
  /** Pixel width of the timeline column. */
  timelineColumnWidthPx: number;
  indentPerDepthPx: number;
  maxIndentPx: number;
  columnGutterPx: number;
}

const DEFAULT_OPTIONS: Required<TimelineRowLayoutOptions> = {
  rowHeightPx: 22,
  rowPaddingPx: 3,
  labelColumnWidthPx: 200,
  minLabelColumnWidthPx: 96,
  maxLabelColumnWidthPx: 420,
  indentPerDepthPx: 10,
  maxIndentPx: 96,
  columnGutterPx: 6,
};

/** Canonical row layout — instantiated once per renderer. */
export class TimelineRowLayout {
  private readonly options: Required<TimelineRowLayoutOptions>;

  constructor(options: TimelineRowLayoutOptions = {}) {
    this.options = { ...DEFAULT_OPTIONS, ...options };
  }

  /** Row height in CSS pixels. */
  rowHeightPx(): number {
    return this.options.rowHeightPx;
  }

  /** Row padding in CSS pixels. */
  rowPaddingPx(): number {
    return this.options.rowPaddingPx;
  }

  /** Indentation per lineage depth in CSS pixels. */
  indentPerDepthPx(): number {
    return this.options.indentPerDepthPx;
  }

  /** Maximum indentation cap. */
  maxIndentPx(): number {
    return this.options.maxIndentPx;
  }

  /** Column gutter in CSS pixels. */
  columnGutterPx(): number {
    return this.options.columnGutterPx;
  }

  /** Indentation a row at ``depth`` carries (clamped). */
  indentForDepth(depth: number): number {
    if (!Number.isFinite(depth) || depth <= 0) return 0;
    const raw = depth * this.options.indentPerDepthPx;
    return Math.min(this.options.maxIndentPx, raw);
  }

  /** Compute the snapshot for the current viewport. */
  resolve(coords: TimelineCoordinateSystem): TimelineRowLayoutSnapshot {
    const cssWidth = coords.viewport.cssWidth;
    const desired = this.options.labelColumnWidthPx;
    const min = this.options.minLabelColumnWidthPx;
    const max = Math.min(this.options.maxLabelColumnWidthPx, Math.max(min, cssWidth - 64));
    const labelColumnWidthPx = Math.min(max, Math.max(min, desired));
    const timelineColumnX = labelColumnWidthPx + this.options.columnGutterPx;
    const timelineColumnWidthPx = Math.max(0, cssWidth - timelineColumnX);
    return {
      rowHeightPx: this.options.rowHeightPx,
      rowPaddingPx: this.options.rowPaddingPx,
      labelColumnWidthPx,
      timelineColumnX,
      timelineColumnWidthPx,
      indentPerDepthPx: this.options.indentPerDepthPx,
      maxIndentPx: this.options.maxIndentPx,
      columnGutterPx: this.options.columnGutterPx,
    };
  }

  /** Top-edge Y of ``rowIndex`` in the snapshot's row space. */
  rowTopY(rowIndex: number, rowStart: number): number {
    return (rowIndex - rowStart) * this.options.rowHeightPx;
  }

  /** Vertical center Y of ``rowIndex``. */
  rowCenterY(rowIndex: number, rowStart: number): number {
    return this.rowTopY(rowIndex, rowStart) + this.options.rowHeightPx / 2;
  }
}

/** Convenience factory for callers that want defaults. */
export function makeRowLayout(options: TimelineRowLayoutOptions = {}): TimelineRowLayout {
  return new TimelineRowLayout(options);
}
