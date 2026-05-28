/**
 * Pool of reusable off-screen canvases.
 *
 * Allocating + GC'ing canvas elements is one of the more expensive
 * operations the browser does; for overlays we frequently want a
 * scratch buffer the size of the visible region. The pool keeps a
 * bounded set of canvases keyed by ``(widthPx, heightPx)`` and hands
 * them out on request.
 *
 * The pool is *abstracted* over the actual canvas factory so tests
 * can swap in a stub. In production we use ``document.createElement``
 * (in browsers) or ``OffscreenCanvas`` (in workers).
 */

import type { BoundedLruStats } from "@/dashboard/timeline/rendering_optimization/utils/bounded_lru";

export interface PooledCanvas {
  readonly width: number;
  readonly height: number;
  /** Returns the underlying canvas element / OffscreenCanvas. */
  readonly canvas: unknown;
}

export interface CanvasFactory {
  create(widthPx: number, heightPx: number): unknown;
}

export const documentCanvasFactory: CanvasFactory = {
  create(widthPx: number, heightPx: number): unknown {
    if (typeof document === "undefined") return { width: widthPx, height: heightPx };
    const c = document.createElement("canvas");
    c.width = Math.max(1, widthPx);
    c.height = Math.max(1, heightPx);
    return c;
  },
};

export interface CanvasPoolStats extends BoundedLruStats {
  /** Canvas allocations that escaped the pool. */
  readonly allocations: number;
  /** Pool checkouts that hit an existing canvas. */
  readonly reuseHits: number;
}

interface PoolEntry {
  readonly key: string;
  readonly value: PooledCanvas;
  inUse: boolean;
}

export class TimelineCanvasPool {
  private readonly entries: PoolEntry[] = [];
  private allocations = 0;
  private reuseHits = 0;
  private hits = 0;
  private misses = 0;
  private evictions = 0;

  constructor(
    private readonly capacity: number,
    private readonly factory: CanvasFactory = documentCanvasFactory,
  ) {
    if (capacity <= 0) {
      throw new RangeError(`canvas-pool capacity must be > 0 (got ${capacity})`);
    }
  }

  acquire(widthPx: number, heightPx: number): PooledCanvas {
    const w = Math.max(1, Math.floor(widthPx));
    const h = Math.max(1, Math.floor(heightPx));
    const key = `${w}x${h}`;
    for (const entry of this.entries) {
      if (!entry.inUse && entry.key === key) {
        entry.inUse = true;
        this.hits += 1;
        this.reuseHits += 1;
        return entry.value;
      }
    }
    this.misses += 1;
    const canvas = this.factory.create(w, h);
    const pooled: PooledCanvas = { width: w, height: h, canvas };
    if (this.entries.length >= this.capacity) {
      // Evict the oldest free entry, if any. If everything's in
      // use we just allocate without retaining the new entry.
      const idx = this.entries.findIndex((e) => !e.inUse);
      if (idx >= 0) {
        this.entries.splice(idx, 1);
        this.evictions += 1;
      } else {
        this.allocations += 1;
        return pooled;
      }
    }
    this.entries.push({ key, value: pooled, inUse: true });
    this.allocations += 1;
    return pooled;
  }

  release(canvas: PooledCanvas): void {
    for (const entry of this.entries) {
      if (entry.value === canvas) {
        entry.inUse = false;
        return;
      }
    }
    // Releasing an unknown canvas is a no-op — never throw, never
    // grow the pool.
  }

  stats(): CanvasPoolStats {
    const total = this.hits + this.misses;
    return {
      size: this.entries.length,
      capacity: this.capacity,
      hits: this.hits,
      misses: this.misses,
      evictions: this.evictions,
      hitRatio: total > 0 ? this.hits / total : 0,
      allocations: this.allocations,
      reuseHits: this.reuseHits,
    };
  }

  clear(): void {
    this.entries.length = 0;
    this.allocations = 0;
    this.reuseHits = 0;
    this.hits = 0;
    this.misses = 0;
    this.evictions = 0;
  }
}
