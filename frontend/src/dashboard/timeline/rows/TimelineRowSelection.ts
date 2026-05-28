/**
 * Selection-aware row painter.
 *
 * Renders the selected-row highlight inside the row column (the label
 * gutter + the timeline gutter). Kept separate from the canonical
 * row renderer so callers can swap in custom selection styles (e.g.
 * focus rings, multi-select) without touching the base row.
 */

import type { TimelineColorPalette } from "@/dashboard/timeline/rendering/TimelineColors";
import type { TimelineRowLayoutSnapshot } from "@/dashboard/timeline/rows/TimelineRowLayout";
import {
  rowReplayFill,
  rowReplayStroke,
  rowSelectionFill,
  rowSelectionStroke,
} from "@/dashboard/timeline/rows/TimelineRowColors";
import type { TimelineRowProjectionEntry } from "@/dashboard/timeline/rows/models/TimelineRowModels";
import type { TimelineRowMetrics } from "@/dashboard/timeline/rows/TimelineRowMetrics";

export interface RowSelectionRenderArgs {
  ctx: CanvasRenderingContext2D;
  palette: TimelineColorPalette;
  layout: TimelineRowLayoutSnapshot;
  rowTopY: number;
  viewportWidth: number;
  row: TimelineRowProjectionEntry;
  selected: boolean;
  metrics?: TimelineRowMetrics;
}

/** Pure: draw the selection band + replay highlight for a single row. */
export function renderRowSelection(args: RowSelectionRenderArgs): void {
  const { ctx, palette, layout, rowTopY, viewportWidth, row, selected, metrics } = args;
  const heightPx = Math.max(1, layout.rowHeightPx);

  if (row.replay !== null && row.replay.focused) {
    ctx.fillStyle = rowReplayFill(palette);
    ctx.fillRect(0, rowTopY, viewportWidth, heightPx);
    ctx.strokeStyle = rowReplayStroke(palette);
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(
      0.5,
      Math.round(rowTopY) + 0.5,
      Math.max(1, viewportWidth - 1),
      Math.max(1, Math.round(heightPx) - 1),
    );
    ctx.setLineDash([]);
  }

  if (!selected) return;
  ctx.fillStyle = rowSelectionFill(palette);
  ctx.fillRect(0, rowTopY, viewportWidth, heightPx);
  ctx.strokeStyle = rowSelectionStroke(palette);
  ctx.lineWidth = 1;
  ctx.strokeRect(
    0.5,
    Math.round(rowTopY) + 0.5,
    Math.max(1, viewportWidth - 1),
    Math.max(1, Math.round(heightPx) - 1),
  );
  metrics?.recordSelection();
}
