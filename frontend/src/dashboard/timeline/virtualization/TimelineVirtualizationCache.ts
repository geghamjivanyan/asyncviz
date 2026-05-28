/**
 * Per-window cache for virtualization results.
 *
 * The cache is keyed by :type:`TimelineViewportWindowSnapshot.key` so
 * back-to-back frames (e.g. hover-only invalidations, cursor moves)
 * hit instead of re-culling. The cache is bounded — when full, it
 * evicts the oldest entry in insertion order.
 *
 * The cache holds *references*, not copies — the underlying arrays
 * come from the spatial index / linear cull and are read-only.
 */

import type { VirtualizationFrame } from "@/dashboard/timeline/virtualization/models/TimelineVirtualizationModels";

const DEFAULT_CAPACITY = 16;

interface CacheEntry<TRow, TSegment> {
  frame: VirtualizationFrame<TRow, TSegment>;
}

export class TimelineVirtualizationCache<TRow, TSegment> {
  private readonly map = new Map<string, CacheEntry<TRow, TSegment>>();
  private capacity: number;
  private _hits = 0;
  private _misses = 0;
  private _evictions = 0;
  private _sequence: number = -1;

  constructor(capacity: number = DEFAULT_CAPACITY) {
    this.capacity = Math.max(2, capacity);
  }

  /** Sync the cache epoch — clears stored entries when the dataset
   *  sequence changes. */
  syncSequence(sequence: number): void {
    if (sequence !== this._sequence) {
      this.map.clear();
      this._sequence = sequence;
    }
  }

  get(key: string): VirtualizationFrame<TRow, TSegment> | null {
    const entry = this.map.get(key);
    if (entry === undefined) {
      this._misses += 1;
      return null;
    }
    // LRU bump.
    this.map.delete(key);
    this.map.set(key, entry);
    this._hits += 1;
    return entry.frame;
  }

  set(key: string, frame: VirtualizationFrame<TRow, TSegment>): void {
    if (this.map.has(key)) this.map.delete(key);
    this.map.set(key, { frame });
    while (this.map.size > this.capacity) {
      const oldest = this.map.keys().next();
      if (oldest.done) break;
      this.map.delete(oldest.value);
      this._evictions += 1;
    }
  }

  clear(): void {
    this.map.clear();
    this._sequence = -1;
  }

  size(): number {
    return this.map.size;
  }

  metrics(): { hits: number; misses: number; evictions: number; sequence: number } {
    return {
      hits: this._hits,
      misses: this._misses,
      evictions: this._evictions,
      sequence: this._sequence,
    };
  }
}
