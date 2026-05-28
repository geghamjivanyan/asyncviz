/**
 * Bounded LRU map shared by the geometry / projection / text caches.
 *
 * Implemented on top of ``Map`` — JS Maps already preserve insertion
 * order, so "touch on read" is a delete-then-set. The implementation
 * is allocation-light: the only per-get cost is a re-insert when the
 * entry is moved to the most-recently-used end.
 */

export interface BoundedLruStats {
  readonly size: number;
  readonly capacity: number;
  readonly hits: number;
  readonly misses: number;
  readonly evictions: number;
  readonly hitRatio: number;
}

export class BoundedLruMap<K, V> {
  private readonly map = new Map<K, V>();
  private _hits = 0;
  private _misses = 0;
  private _evictions = 0;

  constructor(private readonly capacity: number) {
    if (capacity <= 0) {
      throw new RangeError(`LRU capacity must be > 0 (got ${capacity})`);
    }
  }

  get(key: K): V | undefined {
    const value = this.map.get(key);
    if (value === undefined) {
      this._misses += 1;
      return undefined;
    }
    this._hits += 1;
    // Touch — move to the MRU end.
    this.map.delete(key);
    this.map.set(key, value);
    return value;
  }

  /** Insert or update. Returns the evicted value (if any) so callers
   *  can release pooled resources. */
  set(key: K, value: V): V | undefined {
    if (this.map.has(key)) {
      this.map.delete(key);
      this.map.set(key, value);
      return undefined;
    }
    let evicted: V | undefined;
    if (this.map.size >= this.capacity) {
      const lruKey = this.map.keys().next().value as K | undefined;
      if (lruKey !== undefined) {
        evicted = this.map.get(lruKey);
        this.map.delete(lruKey);
        this._evictions += 1;
      }
    }
    this.map.set(key, value);
    return evicted;
  }

  has(key: K): boolean {
    return this.map.has(key);
  }

  delete(key: K): boolean {
    return this.map.delete(key);
  }

  clear(): void {
    this.map.clear();
  }

  get size(): number {
    return this.map.size;
  }

  resetStats(): void {
    this._hits = 0;
    this._misses = 0;
    this._evictions = 0;
  }

  stats(): BoundedLruStats {
    const total = this._hits + this._misses;
    return {
      size: this.map.size,
      capacity: this.capacity,
      hits: this._hits,
      misses: this._misses,
      evictions: this._evictions,
      hitRatio: total > 0 ? this._hits / total : 0,
    };
  }

  /** Iterate from LRU → MRU. */
  *entries(): IterableIterator<[K, V]> {
    yield* this.map.entries();
  }
}
