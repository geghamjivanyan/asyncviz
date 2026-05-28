/**
 * Pure hit testing for freeze-region overlays.
 *
 * The canvas renderer maintains a list of currently visible regions
 * (after culling). The container snapshots the list once per frame
 * and hit-tests pointer events against it via
 * :func:`hitTestFreezeRegions`.
 *
 * Because freeze overlays cover every row vertically (full canvas
 * height), the test is one-dimensional — x only.
 */

import type {
  FreezeRegionGeometry,
  FreezeRegionView,
} from "@/dashboard/timeline/freeze_regions/models/FreezeRegionModels";
import { pointInGeometry } from "@/dashboard/timeline/freeze_regions/FreezeRegionGeometry";

export interface FreezeHitTestEntry {
  region: FreezeRegionView;
  geometry: FreezeRegionGeometry;
}

export interface FreezeHitTestResult {
  region: FreezeRegionView;
  geometry: FreezeRegionGeometry;
  /** Distance from pointer to the freeze body (0 when inside). */
  distanceX: number;
}

/**
 * Find the freeze region under ``xCss`` on this frame.
 *
 * Visibility / sort order is the caller's responsibility — the
 * function picks the smallest matching region so a freeze that's
 * nested inside another wider freeze still wins. Returns ``null`` when
 * no region covers the pointer.
 */
export function hitTestFreezeRegions(
  entries: readonly FreezeHitTestEntry[],
  xCss: number,
): FreezeHitTestResult | null {
  let winner: FreezeHitTestResult | null = null;
  for (const { region, geometry } of entries) {
    if (!pointInGeometry(geometry, xCss)) continue;
    const distanceX = 0;
    if (winner === null || geometry.width < winner.geometry.width) {
      winner = { region, geometry, distanceX };
    }
  }
  return winner;
}

/**
 * Find the nearest freeze region to ``xCss`` within ``toleranceXPx``.
 *
 * Used by keyboard nav and "find nearest freeze" buttons; ignores
 * hover state entirely. Returns ``null`` when nothing is in range.
 */
export function nearestFreezeRegion(
  entries: readonly FreezeHitTestEntry[],
  xCss: number,
  toleranceXPx: number,
): FreezeHitTestResult | null {
  let best: FreezeHitTestResult | null = null;
  for (const { region, geometry } of entries) {
    let distanceX: number;
    if (xCss < geometry.xStart) distanceX = geometry.xStart - xCss;
    else if (xCss > geometry.xEnd) distanceX = xCss - geometry.xEnd;
    else distanceX = 0;
    if (distanceX > toleranceXPx) continue;
    if (best === null || distanceX < best.distanceX) {
      best = { region, geometry, distanceX };
    }
  }
  return best;
}
