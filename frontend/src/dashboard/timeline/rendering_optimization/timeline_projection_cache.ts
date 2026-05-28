/**
 * Projection cache.
 *
 * Stores derived viewport projections (e.g. visible-row windows,
 * culled-segment arrays, replay-frame projections) keyed by their
 * input fingerprint. Unlike the geometry cache, projections are
 * deeper structures, so the capacity is small + the eviction cost is
 * higher per entry.
 *
 * Replay-safe semantics: a fingerprint must encode every input that
 * affects the projection — dataset sequence + camera + viewport
 * dimensions + degradation step. Two callers asking for the same
 * fingerprint receive the *same* object instance (referential
 * equality), so downstream React components can short-circuit.
 */

import {
  BoundedLruMap,
  type BoundedLruStats,
} from "@/dashboard/timeline/rendering_optimization/utils/bounded_lru";

export interface ProjectionEntry<P = unknown> {
  /** Cached projection payload. Treated as immutable by the cache. */
  readonly value: P;
  /** Wall-clock time the projection was inserted (ms). */
  readonly insertedAtMs: number;
}

export interface ProjectionCacheStats extends BoundedLruStats {
  /** Reusable-projection hits (where downstream got a referentially
   *  identical object). */
  readonly reuseHits: number;
}

export class TimelineProjectionCache {
  private readonly entries: BoundedLruMap<string, ProjectionEntry>;
  private reuseHits = 0;

  constructor(capacity: number) {
    this.entries = new BoundedLruMap(capacity);
  }

  /** Return the cached projection (typed). The caller must know the
   *  expected payload shape. */
  get<P>(fingerprint: string): P | undefined {
    const entry = this.entries.get(fingerprint) as ProjectionEntry<P> | undefined;
    if (entry === undefined) return undefined;
    this.reuseHits += 1;
    return entry.value;
  }

  set<P>(fingerprint: string, value: P): void {
    const insertedAtMs = typeof performance !== "undefined" ? performance.now() : Date.now();
    this.entries.set(fingerprint, { value, insertedAtMs });
  }

  /** Compute-or-fetch. The compute callback runs once per unique
   *  fingerprint; subsequent calls reuse the referenced object. */
  getOrCompute<P>(fingerprint: string, compute: () => P): P {
    const cached = this.get<P>(fingerprint);
    if (cached !== undefined) return cached;
    const fresh = compute();
    this.set<P>(fingerprint, fresh);
    return fresh;
  }

  stats(): ProjectionCacheStats {
    return {
      ...this.entries.stats(),
      reuseHits: this.reuseHits,
    };
  }

  clear(): void {
    this.entries.clear();
    this.reuseHits = 0;
  }
}
