/**
 * Observability counters for segment rendering.
 *
 * Mirrors the established pattern used by
 * :class:`TimelineRendererMetrics` and :class:`TimelineRowMetrics` —
 * one class per subsystem, frozen snapshot view, module-level lazy
 * singleton plus a reset helper for tests.
 */

export interface TimelineSegmentMetricsSnapshot {
  segmentsRendered: number;
  visibleSegmentsTotal: number;
  segmentsCulled: number;
  warningsRendered: number;
  selectionsRendered: number;
  decoratorsRendered: number;
  hitTestsPerformed: number;
  projectionsBuilt: number;
  projectionTotalMs: number;
  projectionMaxMs: number;
  geometryComputations: number;
  geometryCacheHits: number;
  geometryCacheMisses: number;
  geometryCacheEvictions: number;
  frameTotalMs: number;
  lastFrameMs: number;
  maxFrameMs: number;
  droppedFrameWarnings: number;
  replayMarkedFrames: number;
  activeSegmentFrames: number;
  overlapsObserved: number;
}

const FRAME_BUDGET_MS = 16;

export class TimelineSegmentMetrics {
  private _segmentsRendered = 0;
  private _visibleSegmentsTotal = 0;
  private _segmentsCulled = 0;
  private _warningsRendered = 0;
  private _selectionsRendered = 0;
  private _decoratorsRendered = 0;
  private _hitTestsPerformed = 0;
  private _projectionsBuilt = 0;
  private _projectionTotalMs = 0;
  private _projectionMaxMs = 0;
  private _geometryComputations = 0;
  private _geometryCacheHits = 0;
  private _geometryCacheMisses = 0;
  private _geometryCacheEvictions = 0;
  private _frameTotalMs = 0;
  private _lastFrameMs = 0;
  private _maxFrameMs = 0;
  private _droppedFrameWarnings = 0;
  private _replayMarkedFrames = 0;
  private _activeSegmentFrames = 0;
  private _overlapsObserved = 0;

  recordSegment(): void {
    this._segmentsRendered += 1;
  }

  recordVisibleSegments(count: number): void {
    if (count > 0) this._visibleSegmentsTotal += count;
  }

  recordCulled(count: number): void {
    if (count > 0) this._segmentsCulled += count;
  }

  recordWarning(): void {
    this._warningsRendered += 1;
  }

  recordSelection(): void {
    this._selectionsRendered += 1;
  }

  recordDecorator(): void {
    this._decoratorsRendered += 1;
  }

  recordHitTest(): void {
    this._hitTestsPerformed += 1;
  }

  recordProjection(durationMs: number): void {
    this._projectionsBuilt += 1;
    if (!Number.isFinite(durationMs) || durationMs < 0) return;
    this._projectionTotalMs += durationMs;
    if (durationMs > this._projectionMaxMs) this._projectionMaxMs = durationMs;
  }

  recordGeometry(args: { hits: number; misses: number; evictions: number }): void {
    if (args.hits > 0) this._geometryCacheHits += args.hits;
    if (args.misses > 0) {
      this._geometryCacheMisses += args.misses;
      this._geometryComputations += args.misses;
    }
    if (args.evictions > 0) this._geometryCacheEvictions += args.evictions;
  }

  recordFrame(args: {
    durationMs: number;
    visibleSegments: number;
    culled: number;
    overlaps: number;
    replayMarked: boolean;
    activeSegments: number;
  }): void {
    this.recordVisibleSegments(args.visibleSegments);
    this.recordCulled(args.culled);
    if (args.overlaps > 0) this._overlapsObserved += args.overlaps;
    if (args.replayMarked) this._replayMarkedFrames += 1;
    if (args.activeSegments > 0) this._activeSegmentFrames += 1;
    if (!Number.isFinite(args.durationMs) || args.durationMs < 0) return;
    this._frameTotalMs += args.durationMs;
    this._lastFrameMs = args.durationMs;
    if (args.durationMs > this._maxFrameMs) this._maxFrameMs = args.durationMs;
    if (args.durationMs > FRAME_BUDGET_MS) this._droppedFrameWarnings += 1;
  }

  snapshot(): TimelineSegmentMetricsSnapshot {
    return {
      segmentsRendered: this._segmentsRendered,
      visibleSegmentsTotal: this._visibleSegmentsTotal,
      segmentsCulled: this._segmentsCulled,
      warningsRendered: this._warningsRendered,
      selectionsRendered: this._selectionsRendered,
      decoratorsRendered: this._decoratorsRendered,
      hitTestsPerformed: this._hitTestsPerformed,
      projectionsBuilt: this._projectionsBuilt,
      projectionTotalMs: this._projectionTotalMs,
      projectionMaxMs: this._projectionMaxMs,
      geometryComputations: this._geometryComputations,
      geometryCacheHits: this._geometryCacheHits,
      geometryCacheMisses: this._geometryCacheMisses,
      geometryCacheEvictions: this._geometryCacheEvictions,
      frameTotalMs: this._frameTotalMs,
      lastFrameMs: this._lastFrameMs,
      maxFrameMs: this._maxFrameMs,
      droppedFrameWarnings: this._droppedFrameWarnings,
      replayMarkedFrames: this._replayMarkedFrames,
      activeSegmentFrames: this._activeSegmentFrames,
      overlapsObserved: this._overlapsObserved,
    };
  }

  reset(): void {
    this._segmentsRendered = 0;
    this._visibleSegmentsTotal = 0;
    this._segmentsCulled = 0;
    this._warningsRendered = 0;
    this._selectionsRendered = 0;
    this._decoratorsRendered = 0;
    this._hitTestsPerformed = 0;
    this._projectionsBuilt = 0;
    this._projectionTotalMs = 0;
    this._projectionMaxMs = 0;
    this._geometryComputations = 0;
    this._geometryCacheHits = 0;
    this._geometryCacheMisses = 0;
    this._geometryCacheEvictions = 0;
    this._frameTotalMs = 0;
    this._lastFrameMs = 0;
    this._maxFrameMs = 0;
    this._droppedFrameWarnings = 0;
    this._replayMarkedFrames = 0;
    this._activeSegmentFrames = 0;
    this._overlapsObserved = 0;
  }
}

let _instance: TimelineSegmentMetrics | null = null;

export function getTimelineSegmentMetrics(): TimelineSegmentMetrics {
  if (_instance === null) _instance = new TimelineSegmentMetrics();
  return _instance;
}

export function resetTimelineSegmentMetrics(): void {
  if (_instance !== null) _instance.reset();
}
