/**
 * Per-camera geometry cache for segments.
 *
 * The geometry cache memoizes the screen-space rect for a (segmentId,
 * cameraKey, viewportKey, layoutKey) tuple. When the camera +
 * viewport + layout are unchanged between frames (the common case
 * during hover, selection-only invalidations, etc.) the cache turns
 * the per-segment projection into an O(1) lookup.
 *
 * The cache is intentionally tiny + bounded: 4096 entries by default,
 * keyed on string concatenation so eviction is predictable.
 */

import type { SegmentScreenRect } from "@/dashboard/timeline/segments/TimelineSegmentGeometry";

const DEFAULT_CAPACITY = 4096;

interface CacheEntry {
  rect: SegmentScreenRect;
}

export class TimelineSegmentGeometryCache {
  private readonly map = new Map<string, CacheEntry>();
  private capacity: number;
  private _hits = 0;
  private _misses = 0;
  private _evictions = 0;
  private _cameraKey = "";
  private _layoutKey = "";

  constructor(capacity: number = DEFAULT_CAPACITY) {
    this.capacity = Math.max(2, capacity);
  }

  /** Reset the cache when the camera / layout fingerprint changes. */
  syncEpoch(cameraKey: string, layoutKey: string): void {
    if (cameraKey !== this._cameraKey || layoutKey !== this._layoutKey) {
      this._cameraKey = cameraKey;
      this._layoutKey = layoutKey;
      this.map.clear();
    }
  }

  get(segmentId: string): SegmentScreenRect | null {
    const entry = this.map.get(segmentId);
    if (entry === undefined) {
      this._misses += 1;
      return null;
    }
    // LRU bump.
    this.map.delete(segmentId);
    this.map.set(segmentId, entry);
    this._hits += 1;
    return entry.rect;
  }

  set(segmentId: string, rect: SegmentScreenRect): void {
    if (this.map.has(segmentId)) this.map.delete(segmentId);
    this.map.set(segmentId, { rect });
    while (this.map.size > this.capacity) {
      const oldest = this.map.keys().next();
      if (oldest.done) break;
      this.map.delete(oldest.value);
      this._evictions += 1;
    }
  }

  clear(): void {
    this.map.clear();
    this._cameraKey = "";
    this._layoutKey = "";
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

  evictions(): number {
    return this._evictions;
  }
}

/** Derive a stable string key from a camera state. */
export function cameraKey(camera: {
  timeStart: number;
  timeEnd: number;
  rowStart: number;
  rowHeight: number;
}): string {
  return `${camera.timeStart}|${camera.timeEnd}|${camera.rowStart}|${camera.rowHeight}`;
}

/** Derive a stable string key from a layout snapshot. */
export function layoutKey(layout: {
  timelineColumnX: number;
  timelineColumnWidthPx: number;
  rowPaddingPx: number;
  minWidthPx: number;
}): string {
  return `${layout.timelineColumnX}|${layout.timelineColumnWidthPx}|${layout.rowPaddingPx}|${layout.minWidthPx}`;
}
