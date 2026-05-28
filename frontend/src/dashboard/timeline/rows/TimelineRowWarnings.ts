/**
 * Warning indicator painter for the row renderer.
 *
 * Draws a small chip on the leading edge of the label column when a
 * row carries an active warning. The chip color is severity-driven;
 * the badge text is the warning count (capped at ``99+``).
 */

import type { TimelineColorPalette } from "@/dashboard/timeline/rendering/TimelineColors";
import type { TimelineRowWarningSeverity } from "@/dashboard/timeline/rendering/TimelineLayer";
import type { TimelineRowLayoutSnapshot } from "@/dashboard/timeline/rows/TimelineRowLayout";
import {
  rowWarningStroke,
  rowWarningTint,
} from "@/dashboard/timeline/rows/TimelineRowColors";
import type { TimelineRowProjectionEntry } from "@/dashboard/timeline/rows/models/TimelineRowModels";
import type { TimelineRowMetrics } from "@/dashboard/timeline/rows/TimelineRowMetrics";

export interface RowWarningRenderArgs {
  ctx: CanvasRenderingContext2D;
  palette: TimelineColorPalette;
  layout: TimelineRowLayoutSnapshot;
  rowTopY: number;
  viewportWidth: number;
  row: TimelineRowProjectionEntry;
  metrics?: TimelineRowMetrics;
}

const BADGE_FONT = "bold 9px ui-sans-serif, system-ui, -apple-system, sans-serif";

/** Pure: draw the warning tint + count chip. No-op when the row is
 *  clean. */
export function renderRowWarnings(args: RowWarningRenderArgs): void {
  const { ctx, palette, layout, rowTopY, viewportWidth, row, metrics } = args;
  if (row.warningSeverity === null || row.warningCount <= 0) return;
  const severity = row.warningSeverity;

  // Full-row warning tint behind the segments.
  ctx.fillStyle = rowWarningTint(palette, severity);
  ctx.fillRect(layout.timelineColumnX, rowTopY, Math.max(0, viewportWidth - layout.timelineColumnX), layout.rowHeightPx);

  drawBadge(ctx, palette, severity, row.warningCount, layout, rowTopY);
  metrics?.recordWarning();
}

function drawBadge(
  ctx: CanvasRenderingContext2D,
  palette: TimelineColorPalette,
  severity: TimelineRowWarningSeverity,
  count: number,
  layout: TimelineRowLayoutSnapshot,
  rowTopY: number,
): void {
  const stroke = rowWarningStroke(palette, severity);
  const text = count > 99 ? "99+" : String(count);
  const padX = 4;
  const badgeHeight = Math.max(10, layout.rowHeightPx - 10);
  const badgeY = rowTopY + Math.max(2, (layout.rowHeightPx - badgeHeight) / 2);

  ctx.save();
  ctx.font = BADGE_FONT;
  const metrics = ctx.measureText(text);
  const badgeWidth = Math.max(badgeHeight, Math.round(metrics.width) + padX * 2);
  const badgeX = Math.max(2, layout.labelColumnWidthPx - badgeWidth - 4);
  ctx.fillStyle = stroke;
  roundedRect(ctx, badgeX, badgeY, badgeWidth, badgeHeight, 4);
  ctx.fill();
  ctx.fillStyle = palette.canvas;
  ctx.textBaseline = "middle";
  ctx.textAlign = "center";
  ctx.fillText(text, badgeX + badgeWidth / 2, badgeY + badgeHeight / 2 + 0.5);
  ctx.restore();
}

function roundedRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
): void {
  const radius = Math.max(0, Math.min(r, w / 2, h / 2));
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + w - radius, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
  ctx.lineTo(x + w, y + h - radius);
  ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
  ctx.lineTo(x + radius, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
}
