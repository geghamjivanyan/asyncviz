/**
 * Selection + replay overlay painter for segments.
 *
 * Both overlays draw on top of the lifecycle fill but underneath the
 * warning ring so they remain visible without hiding severity cues.
 * Replay-focused segments get an additional dashed stroke so they
 * read as "in flight" without becoming the primary selection cue.
 */

import {
  crispStrokeRect,
  type SegmentScreenRect,
} from "@/dashboard/timeline/segments/TimelineSegmentGeometry";

export interface SegmentSelectionArgs {
  ctx: CanvasRenderingContext2D;
  rect: SegmentScreenRect;
  selection: { fill: string; stroke: string } | null;
  replay: { fill: string; stroke: string; focused: boolean } | null;
}

export function renderSegmentSelection(args: SegmentSelectionArgs): void {
  const { ctx, rect, selection, replay } = args;

  if (replay !== null) {
    ctx.save();
    ctx.fillStyle = replay.fill;
    ctx.fillRect(rect.x, rect.y, rect.width, rect.height);
    if (replay.focused) {
      const crisp = crispStrokeRect(rect);
      ctx.strokeStyle = replay.stroke;
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 2]);
      ctx.strokeRect(crisp.x, crisp.y, crisp.width, crisp.height);
      ctx.setLineDash([]);
    }
    ctx.restore();
  }

  if (selection !== null) {
    ctx.save();
    ctx.fillStyle = selection.fill;
    ctx.fillRect(rect.x, rect.y, rect.width, rect.height);
    const crisp = crispStrokeRect(rect);
    ctx.strokeStyle = selection.stroke;
    ctx.lineWidth = 1;
    ctx.strokeRect(crisp.x, crisp.y, crisp.width, crisp.height);
    ctx.restore();
  }
}
