/**
 * Warning overlay painter for segments.
 *
 * Draws a 1-pixel outline around segments whose owning task carries
 * an active warning. The outline color escalates with severity; the
 * intent is to keep the warning visible without overpainting the
 * underlying lifecycle color.
 */

import type { SegmentScreenRect } from "@/dashboard/timeline/segments/TimelineSegmentGeometry";
import { crispStrokeRect } from "@/dashboard/timeline/segments/TimelineSegmentGeometry";

export interface SegmentWarningRenderArgs {
  ctx: CanvasRenderingContext2D;
  rect: SegmentScreenRect;
  color: string;
}

export function renderSegmentWarning(args: SegmentWarningRenderArgs): void {
  const { ctx, rect, color } = args;
  const crisp = crispStrokeRect(rect);
  if (crisp.width <= 0 || crisp.height <= 0) return;
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.25;
  ctx.strokeRect(crisp.x, crisp.y, crisp.width, crisp.height);
  ctx.restore();
}
