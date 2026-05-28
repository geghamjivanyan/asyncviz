/**
 * Pure row hit-testing helpers.
 *
 * Translates a pointer position into the row underneath it. Built on
 * top of the row projection + the camera so the math stays consistent
 * with rendering.
 *
 * The module is intentionally minimal — it does NOT classify the
 * pointer as "in label column" vs "in timeline column" yet; that
 * decision is layered in via the row interaction module.
 */

import type { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import type { TimelineRowLayoutSnapshot } from "@/dashboard/timeline/rows/TimelineRowLayout";
import type { TimelineRowProjectionEntry } from "@/dashboard/timeline/rows/models/TimelineRowModels";
import type { TimelineRowMetrics } from "@/dashboard/timeline/rows/TimelineRowMetrics";

export type TimelineRowZone = "label" | "timeline" | "gutter";

export interface RowHitTestArgs {
  xCss: number;
  yCss: number;
  coords: TimelineCoordinateSystem;
  layout: TimelineRowLayoutSnapshot;
  rows: readonly TimelineRowProjectionEntry[];
  metrics?: TimelineRowMetrics;
}

export interface RowHitTestResult {
  /** Row under the pointer, or ``null`` when the pointer is outside. */
  row: TimelineRowProjectionEntry | null;
  /** Zone the pointer landed in. */
  zone: TimelineRowZone | null;
  /** World seconds at the pointer x; ``null`` when outside the
   *  timeline column. */
  timeSeconds: number | null;
  /** Pointer's row index (fractional) in row-space. */
  rowIndexFractional: number;
}

/** Pure: locate the row under the pointer. */
export function hitTestRow(args: RowHitTestArgs): RowHitTestResult {
  const { xCss, yCss, coords, layout, rows, metrics } = args;
  metrics?.recordHitTest();

  const rowIndexFractional = coords.yToRow(yCss);
  const rowIndex = Math.floor(rowIndexFractional);

  let row: TimelineRowProjectionEntry | null = null;
  if (rowIndex >= 0 && rowIndex < rows.length) {
    row = rows[rowIndex] ?? null;
  }

  let zone: TimelineRowZone | null = null;
  if (row !== null) {
    if (xCss < 0 || xCss > coords.viewport.cssWidth) {
      zone = null;
    } else if (xCss < layout.labelColumnWidthPx) {
      zone = "label";
    } else if (xCss < layout.timelineColumnX) {
      zone = "gutter";
    } else {
      zone = "timeline";
    }
  }

  const timeSeconds =
    zone === "timeline"
      ? coords.xToTime(xCss - layout.timelineColumnX) + coords.camera.timeStart
      : null;

  return { row, zone, timeSeconds, rowIndexFractional };
}

/** Pure: bounding box for a row in CSS pixel space — handy for tests
 *  and future drag-selection. */
export function rowBoundingBox(args: {
  rowIndex: number;
  coords: TimelineCoordinateSystem;
  layout: TimelineRowLayoutSnapshot;
}): { x: number; y: number; width: number; height: number } {
  const { rowIndex, coords, layout } = args;
  const y = coords.rowToY(rowIndex);
  return {
    x: 0,
    y,
    width: coords.viewport.cssWidth,
    height: layout.rowHeightPx,
  };
}
