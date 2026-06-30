/**
 * Dirty-region value type.
 *
 * The coordinate space is *CSS pixels* — the same space the renderer
 * uses for drawing. Regions are inclusive on the low edge, exclusive
 * on the high edge.
 */

export interface DirtyRegion {
  /** Left edge (CSS px). */
  readonly x: number;
  /** Top edge (CSS px). */
  readonly y: number;
  /** Width (CSS px). Always > 0. */
  readonly width: number;
  /** Height (CSS px). Always > 0. */
  readonly height: number;
  /** Why the region is dirty — used by diagnostics + tracing. */
  readonly reason: DirtyRegionReason;
}

export type DirtyRegionReason =
  "data" | "camera" | "viewport" | "selection" | "overlay" | "cursor" | "replay" | "manual";

export const FULL_REGION_SENTINEL: DirtyRegion = {
  x: 0,
  y: 0,
  width: Number.POSITIVE_INFINITY,
  height: Number.POSITIVE_INFINITY,
  reason: "manual",
};

export function isFullRegion(region: DirtyRegion): boolean {
  return !Number.isFinite(region.width) || !Number.isFinite(region.height);
}

export function regionArea(region: DirtyRegion): number {
  if (isFullRegion(region)) return Number.POSITIVE_INFINITY;
  return region.width * region.height;
}

export function regionsOverlap(a: DirtyRegion, b: DirtyRegion): boolean {
  if (isFullRegion(a) || isFullRegion(b)) return true;
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
}

export function mergeRegions(a: DirtyRegion, b: DirtyRegion): DirtyRegion {
  if (isFullRegion(a)) return a;
  if (isFullRegion(b)) return b;
  const x = Math.min(a.x, b.x);
  const y = Math.min(a.y, b.y);
  const right = Math.max(a.x + a.width, b.x + b.width);
  const bottom = Math.max(a.y + a.height, b.y + b.height);
  return {
    x,
    y,
    width: right - x,
    height: bottom - y,
    reason: a.reason === b.reason ? a.reason : "manual",
  };
}
