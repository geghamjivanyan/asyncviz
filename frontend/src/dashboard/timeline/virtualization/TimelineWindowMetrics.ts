/**
 * Observability counters for the virtualization engine.
 */

export interface TimelineWindowMetricsSnapshot {
  windowResolutions: number;
  windowCacheHits: number;
  rowCulls: number;
  visibleRowsTotal: number;
  rowsCulledTotal: number;
  segmentCulls: number;
  visibleSegmentsTotal: number;
  segmentsCulledTotal: number;
  cacheHits: number;
  cacheMisses: number;
  cacheEvictions: number;
  indexBuilds: number;
  spatialQueries: number;
  spatialLookups: number;
  recalculationTotalMs: number;
  lastRecalculationMs: number;
  maxRecalculationMs: number;
  recalculationsOverBudget: number;
  invalidationsObserved: number;
}

const RECALC_BUDGET_MS = 4;

export class TimelineWindowMetrics {
  private _windowResolutions = 0;
  private _windowCacheHits = 0;
  private _rowCulls = 0;
  private _visibleRowsTotal = 0;
  private _rowsCulledTotal = 0;
  private _segmentCulls = 0;
  private _visibleSegmentsTotal = 0;
  private _segmentsCulledTotal = 0;
  private _cacheHits = 0;
  private _cacheMisses = 0;
  private _cacheEvictions = 0;
  private _indexBuilds = 0;
  private _spatialQueries = 0;
  private _spatialLookups = 0;
  private _recalculationTotalMs = 0;
  private _lastRecalculationMs = 0;
  private _maxRecalculationMs = 0;
  private _recalculationsOverBudget = 0;
  private _invalidationsObserved = 0;

  recordWindowResolution(args: { fromCache: boolean }): void {
    this._windowResolutions += 1;
    if (args.fromCache) this._windowCacheHits += 1;
  }

  recordRowCull(args: { visible: number; total: number }): void {
    this._rowCulls += 1;
    this._visibleRowsTotal += Math.max(0, args.visible);
    this._rowsCulledTotal += Math.max(0, args.total - args.visible);
  }

  recordSegmentCull(args: { visible: number; total: number }): void {
    this._segmentCulls += 1;
    this._visibleSegmentsTotal += Math.max(0, args.visible);
    this._segmentsCulledTotal += Math.max(0, args.total - args.visible);
  }

  recordCacheLookup(hit: boolean): void {
    if (hit) this._cacheHits += 1;
    else this._cacheMisses += 1;
  }

  recordCacheEviction(count: number): void {
    if (count > 0) this._cacheEvictions += count;
  }

  recordIndexBuild(count: number): void {
    if (count > 0) this._indexBuilds += count;
  }

  recordSpatial(args: { queries: number; lookups: number }): void {
    if (args.queries > 0) this._spatialQueries += args.queries;
    if (args.lookups > 0) this._spatialLookups += args.lookups;
  }

  recordRecalculation(durationMs: number): void {
    if (!Number.isFinite(durationMs) || durationMs < 0) return;
    this._recalculationTotalMs += durationMs;
    this._lastRecalculationMs = durationMs;
    if (durationMs > this._maxRecalculationMs) this._maxRecalculationMs = durationMs;
    if (durationMs > RECALC_BUDGET_MS) this._recalculationsOverBudget += 1;
  }

  recordInvalidation(): void {
    this._invalidationsObserved += 1;
  }

  snapshot(): TimelineWindowMetricsSnapshot {
    return {
      windowResolutions: this._windowResolutions,
      windowCacheHits: this._windowCacheHits,
      rowCulls: this._rowCulls,
      visibleRowsTotal: this._visibleRowsTotal,
      rowsCulledTotal: this._rowsCulledTotal,
      segmentCulls: this._segmentCulls,
      visibleSegmentsTotal: this._visibleSegmentsTotal,
      segmentsCulledTotal: this._segmentsCulledTotal,
      cacheHits: this._cacheHits,
      cacheMisses: this._cacheMisses,
      cacheEvictions: this._cacheEvictions,
      indexBuilds: this._indexBuilds,
      spatialQueries: this._spatialQueries,
      spatialLookups: this._spatialLookups,
      recalculationTotalMs: this._recalculationTotalMs,
      lastRecalculationMs: this._lastRecalculationMs,
      maxRecalculationMs: this._maxRecalculationMs,
      recalculationsOverBudget: this._recalculationsOverBudget,
      invalidationsObserved: this._invalidationsObserved,
    };
  }

  reset(): void {
    this._windowResolutions = 0;
    this._windowCacheHits = 0;
    this._rowCulls = 0;
    this._visibleRowsTotal = 0;
    this._rowsCulledTotal = 0;
    this._segmentCulls = 0;
    this._visibleSegmentsTotal = 0;
    this._segmentsCulledTotal = 0;
    this._cacheHits = 0;
    this._cacheMisses = 0;
    this._cacheEvictions = 0;
    this._indexBuilds = 0;
    this._spatialQueries = 0;
    this._spatialLookups = 0;
    this._recalculationTotalMs = 0;
    this._lastRecalculationMs = 0;
    this._maxRecalculationMs = 0;
    this._recalculationsOverBudget = 0;
    this._invalidationsObserved = 0;
  }
}

let _instance: TimelineWindowMetrics | null = null;

export function getTimelineWindowMetrics(): TimelineWindowMetrics {
  if (_instance === null) _instance = new TimelineWindowMetrics();
  return _instance;
}

export function resetTimelineWindowMetrics(): void {
  if (_instance !== null) _instance.reset();
}
