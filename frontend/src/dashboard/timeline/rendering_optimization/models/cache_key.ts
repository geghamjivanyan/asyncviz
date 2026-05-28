/**
 * Cache-key value types.
 *
 * Geometry + text + projection caches all share a stringification
 * surface: deterministic, prefix-tagged, allocation-light.
 */

export type CacheNamespace =
  | "geometry"
  | "projection"
  | "text"
  | "overlay"
  | "replay";

/** Deterministic string key — namespace plus stable identifier. */
export function makeCacheKey(namespace: CacheNamespace, identity: string): string {
  return `${namespace}::${identity}`;
}

/** Versioned key for content that depends on a monotonic sequence. */
export function makeVersionedKey(
  namespace: CacheNamespace,
  identity: string,
  version: number,
): string {
  return `${namespace}::${identity}@${version}`;
}

/** Quantize a floating-point coord so trivial sub-pixel deltas hit the
 *  same cache entry. */
export function quantizeCoord(value: number, step: number): number {
  if (step <= 0) return value;
  return Math.round(value / step) * step;
}
