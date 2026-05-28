/**
 * Pure hit-testing helpers for canvas pointer events.
 *
 * Translate a pixel position into (row, segment | null). The renderer
 * doesn't run this every frame — only on pointer move/click. Pure so
 * tests can drive it without a canvas.
 */

import type { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import type {
  TimelineRenderSegment,
  TimelineRow,
} from "@/dashboard/timeline/rendering/TimelineLayer";

export interface HitTestResult {
  row: TimelineRow | null;
  segment: TimelineRenderSegment | null;
  timeSeconds: number;
}

export function hitTest(args: {
  xCss: number;
  yCss: number;
  coords: TimelineCoordinateSystem;
  rows: readonly TimelineRow[];
  segments: readonly TimelineRenderSegment[];
}): HitTestResult {
  const { xCss, yCss, coords, rows, segments } = args;
  const timeSeconds = coords.xToTime(xCss);
  const rowIndex = Math.floor(coords.yToRow(yCss));
  const row = rows.find((r) => r.rowIndex === rowIndex) ?? null;
  let segment: TimelineRenderSegment | null = null;
  if (row !== null) {
    for (const seg of segments) {
      if (seg.rowIndex !== rowIndex) continue;
      if (timeSeconds < seg.startSeconds || timeSeconds > seg.endSeconds) continue;
      segment = seg;
      break;
    }
  }
  return { row, segment, timeSeconds };
}
