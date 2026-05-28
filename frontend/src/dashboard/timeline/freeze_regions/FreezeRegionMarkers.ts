/**
 * Marker drawing helpers for the freeze-region renderer.
 *
 * Markers are 1-pixel vertical strokes that delineate the freeze
 * start / end / escalation moments. Splitting them out keeps the
 * renderer's :meth:`render` body focused on bookkeeping; each helper
 * is pure with respect to the canvas state (caller is responsible for
 * ``save`` / ``restore``).
 */

import type { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import type {
  FreezeRegionGeometry,
  FreezeRegionView,
} from "@/dashboard/timeline/freeze_regions/models/FreezeRegionModels";
import type { FreezeRegionPalette } from "@/dashboard/timeline/freeze_regions/FreezeRegionColors";
import { snapMarkerX } from "@/dashboard/timeline/freeze_regions/FreezeRegionGeometry";

/**
 * Tracing-friendly summary the renderer can fold into its own metrics.
 */
export interface MarkerRenderSummary {
  startMarkers: number;
  endMarkers: number;
  escalationMarkers: number;
}

/** Draw start / end markers for one freeze region. */
export function drawFreezeEdgeMarkers(args: {
  ctx: CanvasRenderingContext2D;
  geometry: FreezeRegionGeometry;
  region: FreezeRegionView;
  palette: FreezeRegionPalette;
  topY: number;
  bottomY: number;
}): { startDrawn: boolean; endDrawn: boolean } {
  const { ctx, geometry, region, palette, topY, bottomY } = args;
  const stroke = palette.marker[region.intent];
  ctx.lineWidth = 1;
  ctx.strokeStyle = stroke;
  let startDrawn = false;
  let endDrawn = false;
  if (!geometry.clippedLeft) {
    const x = snapMarkerX(geometry.xStart);
    ctx.beginPath();
    ctx.moveTo(x, topY);
    ctx.lineTo(x, bottomY);
    ctx.stroke();
    startDrawn = true;
  }
  if (!geometry.clippedRight) {
    const x = snapMarkerX(geometry.xEnd);
    ctx.beginPath();
    ctx.moveTo(x, topY);
    ctx.lineTo(x, bottomY);
    ctx.stroke();
    endDrawn = true;
  }
  return { startDrawn, endDrawn };
}

/**
 * Draw escalation markers for a freeze region — one dashed tick per
 * recorded escalation, mapped through ``coords.timeToX`` from the
 * escalation's monotonic-ns instant.
 *
 * The escalation history is bounded by the emitter (≤ 16 entries), so
 * a linear pass is fine.
 */
export function drawEscalationMarkers(args: {
  ctx: CanvasRenderingContext2D;
  region: FreezeRegionView;
  escalations: ReadonlyArray<{ monotonic_ns: number }>;
  coords: TimelineCoordinateSystem;
  palette: FreezeRegionPalette;
  topY: number;
  bottomY: number;
}): number {
  const { ctx, region, escalations, coords, palette, topY, bottomY } = args;
  if (escalations.length === 0) return 0;
  ctx.save();
  ctx.lineWidth = 1;
  ctx.strokeStyle = palette.escalationMarker;
  ctx.setLineDash([2, 2]);
  let drawn = 0;
  for (const entry of escalations) {
    const seconds = entry.monotonic_ns / 1e9;
    if (seconds < region.startSeconds || seconds > region.endSeconds) continue;
    if (!coords.intersectsTime(seconds, seconds)) continue;
    const x = snapMarkerX(coords.timeToX(seconds));
    if (x < 0 || x > coords.viewport.cssWidth) continue;
    ctx.beginPath();
    ctx.moveTo(x, topY);
    ctx.lineTo(x, bottomY);
    ctx.stroke();
    drawn += 1;
  }
  ctx.setLineDash([]);
  ctx.restore();
  return drawn;
}
