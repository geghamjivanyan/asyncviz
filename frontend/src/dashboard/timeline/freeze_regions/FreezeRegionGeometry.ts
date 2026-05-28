/**
 * Pure geometry helpers for freeze-region rendering.
 *
 * Splitting this out from :class:`FreezeRegionRenderer` keeps the
 * math testable in isolation (no canvas mocks) and unblocks the
 * future heatmap / profiler overlays that need the same world→screen
 * math but render their own visuals.
 *
 * All inputs are primitives + the shared
 * :class:`TimelineCoordinateSystem`; outputs are immutable value
 * objects.
 */

import type { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import type {
  FreezeRegionGeometry,
  FreezeRegionView,
} from "@/dashboard/timeline/freeze_regions/models/FreezeRegionModels";

/** Minimum on-screen width so collapsed regions stay clickable. */
export const MIN_FREEZE_PIXEL_WIDTH = 1.5;

/**
 * Compute the screen geometry for a freeze region against the current
 * coordinate system. Returns ``null`` when the freeze is entirely
 * outside the visible window.
 */
export function computeFreezeGeometry(
  region: FreezeRegionView,
  coords: TimelineCoordinateSystem,
): FreezeRegionGeometry | null {
  if (!coords.intersectsTime(region.startSeconds, region.endSeconds)) return null;
  const cameraStart = coords.camera.timeStart;
  const cameraEnd = coords.camera.timeEnd;
  const viewportWidth = coords.viewport.cssWidth;
  if (viewportWidth <= 0) return null;

  const rawXStart = coords.timeToX(region.startSeconds);
  const rawXEnd = coords.timeToX(region.endSeconds);
  const xStart = Math.max(0, rawXStart);
  const xEnd = Math.min(viewportWidth, rawXEnd);
  const width = Math.max(MIN_FREEZE_PIXEL_WIDTH, xEnd - xStart);

  return {
    groupId: region.groupId,
    xStart,
    xEnd: xStart + width,
    width,
    fullyVisible: region.startSeconds >= cameraStart && region.endSeconds <= cameraEnd,
    clippedLeft: region.startSeconds < cameraStart,
    clippedRight: region.endSeconds > cameraEnd,
  };
}

/**
 * Cull a list of freeze regions to those that intersect the viewport.
 *
 * Pure + side-effect free; returns a new array. The ordering of the
 * input is preserved — callers should sort beforehand (typically via
 * :func:`compareFreezeKeys`) so recovered overlays render first and
 * active overlays on top.
 */
export function cullVisibleFreezeRegions(
  regions: readonly FreezeRegionView[],
  coords: TimelineCoordinateSystem,
): { region: FreezeRegionView; geometry: FreezeRegionGeometry }[] {
  const out: { region: FreezeRegionView; geometry: FreezeRegionGeometry }[] = [];
  for (const region of regions) {
    const geometry = computeFreezeGeometry(region, coords);
    if (geometry !== null) out.push({ region, geometry });
  }
  return out;
}

/** Pure point-in-region test against pre-computed geometry. */
export function pointInGeometry(geometry: FreezeRegionGeometry, x: number): boolean {
  return x >= geometry.xStart && x <= geometry.xEnd;
}

/** Compute the marker X for a freeze edge (snapped to half-pixel for crisp 1px strokes). */
export function snapMarkerX(x: number): number {
  return Math.round(x) + 0.5;
}
