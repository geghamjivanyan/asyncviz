/**
 * Observability counters for the row renderer.
 *
 * Mirrors the established pattern used by
 * :class:`TimelineRendererMetrics` — one class per subsystem, frozen
 * snapshot view, module-level lazy singleton plus a reset helper for
 * tests.
 */

export interface TimelineRowMetricsSnapshot {
  /** Total renderRow() invocations across the renderer's lifetime. */
  rowsRendered: number;
  /** Total visible rows observed (sum across frames). */
  visibleRowsTotal: number;
  /** Total label render invocations. */
  labelsRendered: number;
  /** Label truncations triggered. */
  labelsTruncated: number;
  /** Selection overlays rendered. */
  selectionsRendered: number;
  /** Warning indicators rendered. */
  warningsRendered: number;
  /** Hit-test evaluations. */
  hitTestsPerformed: number;
  /** Projection rebuilds. */
  projectionsBuilt: number;
  /** Sum of projection build durations (ms). */
  projectionTotalMs: number;
  /** Max projection build duration (ms). */
  projectionMaxMs: number;
  /** Sum of frame durations for the row layer (ms). */
  frameTotalMs: number;
  /** Last observed frame duration (ms). */
  lastFrameMs: number;
  /** Max observed frame duration (ms). */
  maxFrameMs: number;
  /** Frame budget overruns observed. */
  droppedFrameWarnings: number;
  /** Text-measurement cache hits. */
  textCacheHits: number;
  /** Text-measurement cache misses. */
  textCacheMisses: number;
  /** Replay-marked frames rendered. */
  replayMarkedFrames: number;
}

const FRAME_BUDGET_MS = 16;

export class TimelineRowMetrics {
  private _rowsRendered = 0;
  private _visibleRowsTotal = 0;
  private _labelsRendered = 0;
  private _labelsTruncated = 0;
  private _selectionsRendered = 0;
  private _warningsRendered = 0;
  private _hitTestsPerformed = 0;
  private _projectionsBuilt = 0;
  private _projectionTotalMs = 0;
  private _projectionMaxMs = 0;
  private _frameTotalMs = 0;
  private _lastFrameMs = 0;
  private _maxFrameMs = 0;
  private _droppedFrameWarnings = 0;
  private _textCacheHits = 0;
  private _textCacheMisses = 0;
  private _replayMarkedFrames = 0;

  recordRow(): void {
    this._rowsRendered += 1;
  }

  recordVisibleRows(count: number): void {
    if (count > 0) this._visibleRowsTotal += count;
  }

  recordLabel(args: { truncated: boolean }): void {
    this._labelsRendered += 1;
    if (args.truncated) this._labelsTruncated += 1;
  }

  recordSelection(): void {
    this._selectionsRendered += 1;
  }

  recordWarning(): void {
    this._warningsRendered += 1;
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

  recordFrame(args: { durationMs: number; visibleRows: number; replayMarked: boolean }): void {
    this.recordVisibleRows(args.visibleRows);
    if (args.replayMarked) this._replayMarkedFrames += 1;
    if (!Number.isFinite(args.durationMs) || args.durationMs < 0) return;
    this._frameTotalMs += args.durationMs;
    this._lastFrameMs = args.durationMs;
    if (args.durationMs > this._maxFrameMs) this._maxFrameMs = args.durationMs;
    if (args.durationMs > FRAME_BUDGET_MS) this._droppedFrameWarnings += 1;
  }

  recordTextCacheHit(): void {
    this._textCacheHits += 1;
  }

  recordTextCacheMiss(): void {
    this._textCacheMisses += 1;
  }

  snapshot(): TimelineRowMetricsSnapshot {
    return {
      rowsRendered: this._rowsRendered,
      visibleRowsTotal: this._visibleRowsTotal,
      labelsRendered: this._labelsRendered,
      labelsTruncated: this._labelsTruncated,
      selectionsRendered: this._selectionsRendered,
      warningsRendered: this._warningsRendered,
      hitTestsPerformed: this._hitTestsPerformed,
      projectionsBuilt: this._projectionsBuilt,
      projectionTotalMs: this._projectionTotalMs,
      projectionMaxMs: this._projectionMaxMs,
      frameTotalMs: this._frameTotalMs,
      lastFrameMs: this._lastFrameMs,
      maxFrameMs: this._maxFrameMs,
      droppedFrameWarnings: this._droppedFrameWarnings,
      textCacheHits: this._textCacheHits,
      textCacheMisses: this._textCacheMisses,
      replayMarkedFrames: this._replayMarkedFrames,
    };
  }

  reset(): void {
    this._rowsRendered = 0;
    this._visibleRowsTotal = 0;
    this._labelsRendered = 0;
    this._labelsTruncated = 0;
    this._selectionsRendered = 0;
    this._warningsRendered = 0;
    this._hitTestsPerformed = 0;
    this._projectionsBuilt = 0;
    this._projectionTotalMs = 0;
    this._projectionMaxMs = 0;
    this._frameTotalMs = 0;
    this._lastFrameMs = 0;
    this._maxFrameMs = 0;
    this._droppedFrameWarnings = 0;
    this._textCacheHits = 0;
    this._textCacheMisses = 0;
    this._replayMarkedFrames = 0;
  }
}

let _instance: TimelineRowMetrics | null = null;

export function getTimelineRowMetrics(): TimelineRowMetrics {
  if (_instance === null) _instance = new TimelineRowMetrics();
  return _instance;
}

export function resetTimelineRowMetrics(): void {
  if (_instance !== null) _instance.reset();
}
