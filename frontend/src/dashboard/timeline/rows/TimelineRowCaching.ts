/**
 * LRU text-metrics cache for row label rendering.
 *
 * Canvas ``measureText`` is fast but not free; across a scrolling
 * timeline we measure the same labels thousands of times per second.
 * The cache keys by ``font|maxWidth|text`` and holds a small bounded
 * pool of resolved truncations. The renderer treats cache hits as
 * already-truncated strings so the slow path runs once per unique
 * label/width pair.
 */

const DEFAULT_CAPACITY = 512;

export interface CachedLabel {
  /** Truncated text ready to draw. */
  text: string;
  /** Measured width in CSS pixels. */
  widthPx: number;
  /** Whether the truncation actually shortened the source label. */
  truncated: boolean;
}

interface CacheEntry extends CachedLabel {
  key: string;
}

/** Bounded LRU cache for text-metric results. */
export class TimelineRowTextCache {
  private map = new Map<string, CacheEntry>();
  private capacity: number;
  private _hits = 0;
  private _misses = 0;

  constructor(capacity: number = DEFAULT_CAPACITY) {
    this.capacity = Math.max(2, capacity);
  }

  get(font: string, maxWidthPx: number, text: string): CachedLabel | null {
    const key = makeKey(font, maxWidthPx, text);
    const entry = this.map.get(key);
    if (entry === undefined) {
      this._misses += 1;
      return null;
    }
    // LRU bump — re-insert to move to the end.
    this.map.delete(key);
    this.map.set(key, entry);
    this._hits += 1;
    return entry;
  }

  set(font: string, maxWidthPx: number, text: string, value: CachedLabel): void {
    const key = makeKey(font, maxWidthPx, text);
    if (this.map.has(key)) this.map.delete(key);
    this.map.set(key, { ...value, key });
    while (this.map.size > this.capacity) {
      const oldest = this.map.keys().next();
      if (oldest.done) break;
      this.map.delete(oldest.value);
    }
  }

  clear(): void {
    this.map.clear();
  }

  size(): number {
    return this.map.size;
  }

  hits(): number {
    return this._hits;
  }

  misses(): number {
    return this._misses;
  }
}

function makeKey(font: string, maxWidthPx: number, text: string): string {
  return `${font}|${Math.max(0, Math.round(maxWidthPx))}|${text}`;
}
