/**
 * Observability counters for the time-scaling engine.
 */

import type { ScaleInvalidationKind } from "@/dashboard/timeline/scaling/TimelineScaleInvalidation";

export interface TimelineScaleMetricsSnapshot {
  scaleChanges: number;
  scaleZooms: number;
  scalePans: number;
  scaleFits: number;
  viewportNormalizations: number;
  precisionWarnings: number;
  constraintHitsMin: number;
  constraintHitsMax: number;
  ticksGenerated: number;
  ticksFromCache: number;
  totalTickGenMs: number;
  lastTickGenMs: number;
  maxTickGenMs: number;
  cacheHits: number;
  cacheMisses: number;
  cacheEvictions: number;
  invalidationsByKind: Record<ScaleInvalidationKind, number>;
  totalNormalizationMs: number;
  lastNormalizationMs: number;
  maxNormalizationMs: number;
}

function emptyInvalidations(): Record<ScaleInvalidationKind, number> {
  return {
    "scale-window": 0,
    viewport: 0,
    constraints: 0,
    manual: 0,
  };
}

export class TimelineScaleMetrics {
  private _scaleChanges = 0;
  private _scaleZooms = 0;
  private _scalePans = 0;
  private _scaleFits = 0;
  private _viewportNormalizations = 0;
  private _precisionWarnings = 0;
  private _constraintHitsMin = 0;
  private _constraintHitsMax = 0;
  private _ticksGenerated = 0;
  private _ticksFromCache = 0;
  private _totalTickGenMs = 0;
  private _lastTickGenMs = 0;
  private _maxTickGenMs = 0;
  private _cacheHits = 0;
  private _cacheMisses = 0;
  private _cacheEvictions = 0;
  private _invalidationsByKind: Record<ScaleInvalidationKind, number> = emptyInvalidations();
  private _totalNormalizationMs = 0;
  private _lastNormalizationMs = 0;
  private _maxNormalizationMs = 0;

  recordScaleChange(kind: "set" | "zoom" | "pan" | "fit"): void {
    this._scaleChanges += 1;
    if (kind === "zoom") this._scaleZooms += 1;
    else if (kind === "pan") this._scalePans += 1;
    else if (kind === "fit") this._scaleFits += 1;
  }

  recordViewportNormalization(durationMs: number, hitFloor: boolean): void {
    this._viewportNormalizations += 1;
    if (hitFloor) this._precisionWarnings += 1;
    if (!Number.isFinite(durationMs) || durationMs < 0) return;
    this._totalNormalizationMs += durationMs;
    this._lastNormalizationMs = durationMs;
    if (durationMs > this._maxNormalizationMs) this._maxNormalizationMs = durationMs;
  }

  recordConstraintHit(edge: "min" | "max"): void {
    if (edge === "min") this._constraintHitsMin += 1;
    else this._constraintHitsMax += 1;
  }

  recordTickGeneration(durationMs: number, fromCache: boolean): void {
    if (fromCache) {
      this._ticksFromCache += 1;
      this._cacheHits += 1;
      return;
    }
    this._ticksGenerated += 1;
    this._cacheMisses += 1;
    if (!Number.isFinite(durationMs) || durationMs < 0) return;
    this._totalTickGenMs += durationMs;
    this._lastTickGenMs = durationMs;
    if (durationMs > this._maxTickGenMs) this._maxTickGenMs = durationMs;
  }

  recordCacheEvictions(count: number): void {
    if (count > 0) this._cacheEvictions += count;
  }

  recordInvalidation(kind: ScaleInvalidationKind): void {
    this._invalidationsByKind[kind] = (this._invalidationsByKind[kind] ?? 0) + 1;
  }

  snapshot(): TimelineScaleMetricsSnapshot {
    return {
      scaleChanges: this._scaleChanges,
      scaleZooms: this._scaleZooms,
      scalePans: this._scalePans,
      scaleFits: this._scaleFits,
      viewportNormalizations: this._viewportNormalizations,
      precisionWarnings: this._precisionWarnings,
      constraintHitsMin: this._constraintHitsMin,
      constraintHitsMax: this._constraintHitsMax,
      ticksGenerated: this._ticksGenerated,
      ticksFromCache: this._ticksFromCache,
      totalTickGenMs: this._totalTickGenMs,
      lastTickGenMs: this._lastTickGenMs,
      maxTickGenMs: this._maxTickGenMs,
      cacheHits: this._cacheHits,
      cacheMisses: this._cacheMisses,
      cacheEvictions: this._cacheEvictions,
      invalidationsByKind: { ...this._invalidationsByKind },
      totalNormalizationMs: this._totalNormalizationMs,
      lastNormalizationMs: this._lastNormalizationMs,
      maxNormalizationMs: this._maxNormalizationMs,
    };
  }

  reset(): void {
    this._scaleChanges = 0;
    this._scaleZooms = 0;
    this._scalePans = 0;
    this._scaleFits = 0;
    this._viewportNormalizations = 0;
    this._precisionWarnings = 0;
    this._constraintHitsMin = 0;
    this._constraintHitsMax = 0;
    this._ticksGenerated = 0;
    this._ticksFromCache = 0;
    this._totalTickGenMs = 0;
    this._lastTickGenMs = 0;
    this._maxTickGenMs = 0;
    this._cacheHits = 0;
    this._cacheMisses = 0;
    this._cacheEvictions = 0;
    this._invalidationsByKind = emptyInvalidations();
    this._totalNormalizationMs = 0;
    this._lastNormalizationMs = 0;
    this._maxNormalizationMs = 0;
  }
}

let _instance: TimelineScaleMetrics | null = null;

export function getTimelineScaleMetrics(): TimelineScaleMetrics {
  if (_instance === null) _instance = new TimelineScaleMetrics();
  return _instance;
}

export function resetTimelineScaleMetrics(): void {
  if (_instance !== null) _instance.reset();
}
