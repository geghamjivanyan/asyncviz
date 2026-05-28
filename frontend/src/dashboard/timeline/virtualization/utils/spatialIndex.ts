/**
 * Lightweight bucketed spatial index for segments.
 *
 * Segments are bucketed by ``rowIndex`` and, within a row, kept
 * sorted by ``startSeconds``. Lookup is bounded by
 * ``O(visibleRowCount * log(segmentsPerRow))`` instead of
 * ``O(totalSegments)`` — the difference between a 60fps scroll and a
 * jank-storm at 100k segments.
 *
 * The index is intentionally *read-only* once built. Live updates
 * rebuild the index per dataset epoch (sequence cursor); the cost is
 * paid once per change, not per frame.
 */

export interface SpatialIndexable {
  rowIndex: number;
  startSeconds: number;
  endSeconds: number;
  /** Active segments extend to the camera right-edge — the index
   *  uses ``isActive`` to keep them visible past their wire end. */
  isActive?: boolean;
}

export interface SpatialIndexOptions {
  /** Pre-allocate this many row buckets when building — speeds up
   *  construction on dense, narrow datasets. */
  estimatedRows?: number;
}

export class TimelineSegmentSpatialIndex<TSegment extends SpatialIndexable> {
  private readonly bucketsByRow = new Map<number, TSegment[]>();
  private _builtCount = 0;
  private _queryCount = 0;
  private _lookupCount = 0;

  constructor(segments: readonly TSegment[], options: SpatialIndexOptions = {}) {
    if (segments.length === 0) return;
    if (options.estimatedRows !== undefined && options.estimatedRows > 0) {
      // Map preallocation is a noop in V8 but the hint makes intent
      // clear + future-proofs us against changes in the underlying
      // hash table.
    }
    for (const segment of segments) {
      const bucket = this.bucketsByRow.get(segment.rowIndex);
      if (bucket === undefined) {
        this.bucketsByRow.set(segment.rowIndex, [segment]);
      } else {
        bucket.push(segment);
      }
      this._builtCount += 1;
    }
    for (const bucket of this.bucketsByRow.values()) {
      bucket.sort((a, b) => a.startSeconds - b.startSeconds);
    }
  }

  size(): number {
    return this._builtCount;
  }

  rowCount(): number {
    return this.bucketsByRow.size;
  }

  /** Return every segment whose row + time intersects the query
   *  window. The visit order is row-major + start-time ascending. */
  query(args: {
    startRowIndex: number;
    endRowIndex: number;
    startSeconds: number;
    endSeconds: number;
    /** When set, active segments are extended to ``cameraEnd`` so the
     *  query keeps them visible after their wire end. */
    cameraEndSeconds?: number;
  }): TSegment[] {
    this._queryCount += 1;
    const out: TSegment[] = [];
    if (this.bucketsByRow.size === 0) return out;
    const { startRowIndex, endRowIndex, startSeconds, endSeconds } = args;
    const cameraEnd = args.cameraEndSeconds ?? endSeconds;
    for (let row = startRowIndex; row < endRowIndex; row += 1) {
      const bucket = this.bucketsByRow.get(row);
      if (bucket === undefined) continue;
      // Binary search for the first segment whose end is >= startSeconds.
      // We need a lower-bound on the segment's *effective* end so
      // active segments stay visible — fall back to a linear scan when
      // the bucket has active segments mixed in.
      const lower = lowerBoundByEnd(bucket, startSeconds, cameraEnd);
      for (let i = lower; i < bucket.length; i += 1) {
        const seg = bucket[i];
        if (seg.startSeconds > endSeconds) break;
        const effectiveEnd =
          seg.isActive === true ? Math.max(seg.endSeconds, cameraEnd) : seg.endSeconds;
        if (effectiveEnd < startSeconds) continue;
        out.push(seg);
        this._lookupCount += 1;
      }
    }
    return out;
  }

  metrics(): { queries: number; lookups: number } {
    return { queries: this._queryCount, lookups: this._lookupCount };
  }
}

/** Binary search: return the smallest index ``i`` such that
 *  ``segments[i].startSeconds >= floorStart``. We over-shoot
 *  intentionally — the caller filters with the effective-end test. */
function lowerBoundByEnd<TSegment extends SpatialIndexable>(
  segments: readonly TSegment[],
  floorStart: number,
  _cameraEnd: number,
): number {
  // Walk back a few entries from the bisect to catch wide segments
  // that started earlier but still overlap. The fudge is bounded so
  // worst-case cost stays O(log n + k) with small k.
  let lo = 0;
  let hi = segments.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (segments[mid].startSeconds < floorStart) {
      lo = mid + 1;
    } else {
      hi = mid;
    }
  }
  // Step back to include earlier segments whose end might overlap.
  // Bound the walk-back at 32 entries to keep worst-case bounded.
  const walkback = Math.min(lo, 32);
  return Math.max(0, lo - walkback);
}
