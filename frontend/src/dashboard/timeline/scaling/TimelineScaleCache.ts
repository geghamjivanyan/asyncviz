/**
 * Bounded LRU caches for tick lists + scale snapshots.
 *
 * Tick generation is cheap individually but scaling-frequent — every
 * frame at 60fps during a zoom gesture is a meaningful budget hit.
 * The cache stores the latest few computed tick lists keyed by the
 * scale's stable key so repeat lookups during a hover-only
 * invalidation are free.
 */

import type { TimelineTickList } from "@/dashboard/timeline/scaling/models/TimelineScaleModels";

const DEFAULT_CAPACITY = 8;

interface TickEntry {
  list: TimelineTickList;
}

export class TimelineScaleTickCache {
  private readonly map = new Map<string, TickEntry>();
  private capacity: number;
  private _hits = 0;
  private _misses = 0;
  private _evictions = 0;

  constructor(capacity: number = DEFAULT_CAPACITY) {
    this.capacity = Math.max(2, capacity);
  }

  get(key: string): TimelineTickList | null {
    const entry = this.map.get(key);
    if (entry === undefined) {
      this._misses += 1;
      return null;
    }
    // LRU bump.
    this.map.delete(key);
    this.map.set(key, entry);
    this._hits += 1;
    return entry.list;
  }

  set(key: string, list: TimelineTickList): void {
    if (this.map.has(key)) this.map.delete(key);
    this.map.set(key, { list });
    while (this.map.size > this.capacity) {
      const oldest = this.map.keys().next();
      if (oldest.done) break;
      this.map.delete(oldest.value);
      this._evictions += 1;
    }
  }

  clear(): void {
    this.map.clear();
  }

  size(): number {
    return this.map.size;
  }

  metrics(): { hits: number; misses: number; evictions: number; size: number } {
    return {
      hits: this._hits,
      misses: this._misses,
      evictions: this._evictions,
      size: this.size(),
    };
  }
}
