/**
 * Render-optimization observability metrics.
 *
 * Thread-safe-by-default (single-threaded JS, but the API mirrors the
 * runtime layers so a worker port is straightforward). The singleton
 * is module-level + reset-able for tests.
 */

import type { DirtyRegionReason } from "@/dashboard/timeline/rendering_optimization/models/dirty_region";

export interface RenderOptimizationMetricsSnapshot {
  readonly framesRendered: number;
  readonly framesSkipped: number;
  readonly framesIncremental: number;
  readonly framesFull: number;
  readonly framesOverBudget: number;
  readonly framesOverHard: number;
  readonly dirtyRegionsProcessed: number;
  readonly dirtyRegionsCollapsed: number;
  readonly dirtyAreaRedrawnPx2: number;
  readonly passesExecuted: number;
  readonly passesSkipped: number;
  readonly passesErrored: number;
  readonly overlayRedraws: number;
  readonly overlayCoalesced: number;
  readonly viewportCullRatioSum: number;
  readonly viewportCullSamples: number;
  readonly cursorKeyframes: number;
  readonly cursorIncrementalRedraws: number;
  readonly degradeEvents: number;
  readonly restoreEvents: number;
  readonly redrawAreaRatioMean: number;
  readonly invalidationsByReason: Readonly<Record<DirtyRegionReason, number>>;
  readonly geometryCacheHits: number;
  readonly geometryCacheMisses: number;
  readonly projectionCacheHits: number;
  readonly projectionCacheMisses: number;
  readonly textCacheHits: number;
  readonly textCacheMisses: number;
  readonly canvasPoolHits: number;
  readonly canvasPoolMisses: number;
}

const EMPTY_REASONS: Record<DirtyRegionReason, number> = {
  data: 0,
  camera: 0,
  viewport: 0,
  selection: 0,
  overlay: 0,
  cursor: 0,
  replay: 0,
  manual: 0,
};

export class RenderOptimizationMetrics {
  private _framesRendered = 0;
  private _framesSkipped = 0;
  private _framesIncremental = 0;
  private _framesFull = 0;
  private _framesOverBudget = 0;
  private _framesOverHard = 0;
  private _dirtyRegionsProcessed = 0;
  private _dirtyRegionsCollapsed = 0;
  private _dirtyAreaRedrawnPx2 = 0;
  private _passesExecuted = 0;
  private _passesSkipped = 0;
  private _passesErrored = 0;
  private _overlayRedraws = 0;
  private _overlayCoalesced = 0;
  private _viewportCullRatioSum = 0;
  private _viewportCullSamples = 0;
  private _cursorKeyframes = 0;
  private _cursorIncrementalRedraws = 0;
  private _degradeEvents = 0;
  private _restoreEvents = 0;
  private _redrawAreaRatioSum = 0;
  private _redrawAreaRatioSamples = 0;
  private _invalidationsByReason: Record<DirtyRegionReason, number> = { ...EMPTY_REASONS };
  private _geometryCacheHits = 0;
  private _geometryCacheMisses = 0;
  private _projectionCacheHits = 0;
  private _projectionCacheMisses = 0;
  private _textCacheHits = 0;
  private _textCacheMisses = 0;
  private _canvasPoolHits = 0;
  private _canvasPoolMisses = 0;

  recordFrame(args: {
    mode: "incremental" | "full" | "skip";
    durationMs: number;
    overBudget: boolean;
    overHardBudget: boolean;
    areaPx2: number;
    canvasAreaPx2: number;
  }): void {
    if (args.mode === "skip") {
      this._framesSkipped += 1;
      return;
    }
    this._framesRendered += 1;
    if (args.mode === "incremental") this._framesIncremental += 1;
    if (args.mode === "full") this._framesFull += 1;
    if (args.overBudget) this._framesOverBudget += 1;
    if (args.overHardBudget) this._framesOverHard += 1;
    this._dirtyAreaRedrawnPx2 += args.areaPx2;
    if (args.canvasAreaPx2 > 0) {
      this._redrawAreaRatioSum += Math.min(1, args.areaPx2 / args.canvasAreaPx2);
      this._redrawAreaRatioSamples += 1;
    }
  }

  recordDirtyRegions(processed: number, collapsed: number): void {
    this._dirtyRegionsProcessed += processed;
    this._dirtyRegionsCollapsed += collapsed;
  }

  recordPass(args: { executed: boolean; skipped: boolean; errored: boolean }): void {
    if (args.executed) this._passesExecuted += 1;
    if (args.skipped) this._passesSkipped += 1;
    if (args.errored) this._passesErrored += 1;
  }

  recordOverlayFlush(redraws: number, coalesced: number): void {
    this._overlayRedraws += redraws;
    this._overlayCoalesced += coalesced;
  }

  recordViewportCullRatio(ratio: number): void {
    if (!Number.isFinite(ratio)) return;
    this._viewportCullRatioSum += ratio;
    this._viewportCullSamples += 1;
  }

  recordCursorKeyframe(): void {
    this._cursorKeyframes += 1;
  }

  recordCursorIncrementalRedraw(): void {
    this._cursorIncrementalRedraws += 1;
  }

  recordDegrade(): void {
    this._degradeEvents += 1;
  }

  recordRestore(): void {
    this._restoreEvents += 1;
  }

  recordInvalidation(reason: DirtyRegionReason): void {
    this._invalidationsByReason[reason] = (this._invalidationsByReason[reason] ?? 0) + 1;
  }

  recordGeometryCache(hits: number, misses: number): void {
    this._geometryCacheHits += hits;
    this._geometryCacheMisses += misses;
  }

  recordProjectionCache(hits: number, misses: number): void {
    this._projectionCacheHits += hits;
    this._projectionCacheMisses += misses;
  }

  recordTextCache(hits: number, misses: number): void {
    this._textCacheHits += hits;
    this._textCacheMisses += misses;
  }

  recordCanvasPool(hits: number, misses: number): void {
    this._canvasPoolHits += hits;
    this._canvasPoolMisses += misses;
  }

  snapshot(): RenderOptimizationMetricsSnapshot {
    return {
      framesRendered: this._framesRendered,
      framesSkipped: this._framesSkipped,
      framesIncremental: this._framesIncremental,
      framesFull: this._framesFull,
      framesOverBudget: this._framesOverBudget,
      framesOverHard: this._framesOverHard,
      dirtyRegionsProcessed: this._dirtyRegionsProcessed,
      dirtyRegionsCollapsed: this._dirtyRegionsCollapsed,
      dirtyAreaRedrawnPx2: this._dirtyAreaRedrawnPx2,
      passesExecuted: this._passesExecuted,
      passesSkipped: this._passesSkipped,
      passesErrored: this._passesErrored,
      overlayRedraws: this._overlayRedraws,
      overlayCoalesced: this._overlayCoalesced,
      viewportCullRatioSum: this._viewportCullRatioSum,
      viewportCullSamples: this._viewportCullSamples,
      cursorKeyframes: this._cursorKeyframes,
      cursorIncrementalRedraws: this._cursorIncrementalRedraws,
      degradeEvents: this._degradeEvents,
      restoreEvents: this._restoreEvents,
      redrawAreaRatioMean:
        this._redrawAreaRatioSamples > 0
          ? this._redrawAreaRatioSum / this._redrawAreaRatioSamples
          : 0,
      invalidationsByReason: { ...this._invalidationsByReason },
      geometryCacheHits: this._geometryCacheHits,
      geometryCacheMisses: this._geometryCacheMisses,
      projectionCacheHits: this._projectionCacheHits,
      projectionCacheMisses: this._projectionCacheMisses,
      textCacheHits: this._textCacheHits,
      textCacheMisses: this._textCacheMisses,
      canvasPoolHits: this._canvasPoolHits,
      canvasPoolMisses: this._canvasPoolMisses,
    };
  }

  reset(): void {
    this._framesRendered = 0;
    this._framesSkipped = 0;
    this._framesIncremental = 0;
    this._framesFull = 0;
    this._framesOverBudget = 0;
    this._framesOverHard = 0;
    this._dirtyRegionsProcessed = 0;
    this._dirtyRegionsCollapsed = 0;
    this._dirtyAreaRedrawnPx2 = 0;
    this._passesExecuted = 0;
    this._passesSkipped = 0;
    this._passesErrored = 0;
    this._overlayRedraws = 0;
    this._overlayCoalesced = 0;
    this._viewportCullRatioSum = 0;
    this._viewportCullSamples = 0;
    this._cursorKeyframes = 0;
    this._cursorIncrementalRedraws = 0;
    this._degradeEvents = 0;
    this._restoreEvents = 0;
    this._redrawAreaRatioSum = 0;
    this._redrawAreaRatioSamples = 0;
    this._invalidationsByReason = { ...EMPTY_REASONS };
    this._geometryCacheHits = 0;
    this._geometryCacheMisses = 0;
    this._projectionCacheHits = 0;
    this._projectionCacheMisses = 0;
    this._textCacheHits = 0;
    this._textCacheMisses = 0;
    this._canvasPoolHits = 0;
    this._canvasPoolMisses = 0;
  }
}

let _instance: RenderOptimizationMetrics | null = null;

export function getRenderOptimizationMetrics(): RenderOptimizationMetrics {
  if (_instance === null) _instance = new RenderOptimizationMetrics();
  return _instance;
}

export function resetRenderOptimizationMetrics(): void {
  if (_instance !== null) _instance.reset();
}
