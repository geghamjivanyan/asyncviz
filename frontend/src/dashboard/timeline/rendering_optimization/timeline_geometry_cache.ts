/**
 * Geometry cache.
 *
 * Caches per-segment + per-row geometry (CSS px x/y/width/height) keyed
 * by the inputs that produced it. The cache is invalidated by version
 * tag — every dataset/camera/viewport mutation bumps the version, so
 * stale geometry never bleeds into a fresh frame.
 *
 * Memory is bounded by the LRU; geometry entries are tiny frozen
 * objects, so the per-entry cost is dominated by the key string.
 */

import {
  makeVersionedKey,
  quantizeCoord,
} from "@/dashboard/timeline/rendering_optimization/models/cache_key";
import {
  BoundedLruMap,
  type BoundedLruStats,
} from "@/dashboard/timeline/rendering_optimization/utils/bounded_lru";

export interface GeometryEntry {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

export interface GeometryCacheStats extends BoundedLruStats {
  /** Version tag the cache currently honors. */
  readonly version: number;
  /** How many times the cache has been version-invalidated. */
  readonly versionResets: number;
}

const QUANTIZE_PX = 0.5;

export class TimelineGeometryCache {
  private readonly entries: BoundedLruMap<string, GeometryEntry>;
  private version = 0;
  private versionResets = 0;

  constructor(capacity: number) {
    this.entries = new BoundedLruMap(capacity);
  }

  /** Bump the version tag — every prior entry is considered stale. */
  bumpVersion(): void {
    this.version += 1;
    this.versionResets += 1;
    this.entries.clear();
  }

  currentVersion(): number {
    return this.version;
  }

  /** Return a cached entry, or ``undefined`` if not present. */
  get(identity: string): GeometryEntry | undefined {
    return this.entries.get(makeVersionedKey("geometry", identity, this.version));
  }

  /** Insert a freshly-computed entry. Inputs are quantized so trivial
   *  sub-pixel jitter doesn't multiply cache entries. */
  set(identity: string, entry: GeometryEntry): void {
    const quantized: GeometryEntry = {
      x: quantizeCoord(entry.x, QUANTIZE_PX),
      y: quantizeCoord(entry.y, QUANTIZE_PX),
      width: quantizeCoord(Math.max(0, entry.width), QUANTIZE_PX),
      height: quantizeCoord(Math.max(0, entry.height), QUANTIZE_PX),
    };
    this.entries.set(makeVersionedKey("geometry", identity, this.version), quantized);
  }

  /** Compute-or-fetch. The compute callback runs only on a miss. */
  getOrCompute(identity: string, compute: () => GeometryEntry): GeometryEntry {
    const cached = this.get(identity);
    if (cached !== undefined) return cached;
    const fresh = compute();
    this.set(identity, fresh);
    return fresh;
  }

  stats(): GeometryCacheStats {
    return {
      ...this.entries.stats(),
      version: this.version,
      versionResets: this.versionResets,
    };
  }

  resetStats(): void {
    this.entries.resetStats();
  }

  clear(): void {
    this.entries.clear();
  }
}
