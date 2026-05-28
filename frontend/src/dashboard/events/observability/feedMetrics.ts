/**
 * Observability counters for the runtime event feed.
 *
 * Mirrors the pattern from :class:`TaskTableMetrics` /
 * :class:`MetricsHeaderMetrics` — one class per subsystem, frozen
 * snapshot view, no module-level singleton needed in tests.
 */

export interface EventFeedMetricsSnapshot {
  projectionRebuilds: number;
  pipelineRuns: number;
  rowRenders: number;
  groupRebuilds: number;
  filterEvaluations: number;
  /** Number of rows appended via the live path. */
  liveAppends: number;
  /** Number of rows appended via the replay path. */
  replayAppends: number;
  /** Total rows projected since the metrics instance was created. */
  rowsProjectedTotal: number;
  lastPipelineMs: number;
  maxPipelineMs: number;
  lastProjectionMs: number;
  maxProjectionMs: number;
  renderStormWarnings: number;
}

const RENDER_STORM_THRESHOLD = 120;

export class EventFeedMetrics {
  private _projectionRebuilds = 0;
  private _pipelineRuns = 0;
  private _rowRenders = 0;
  private _groupRebuilds = 0;
  private _filterEvaluations = 0;
  private _liveAppends = 0;
  private _replayAppends = 0;
  private _rowsProjectedTotal = 0;
  private _lastPipelineMs = 0;
  private _maxPipelineMs = 0;
  private _lastProjectionMs = 0;
  private _maxProjectionMs = 0;
  private _renderStormWarnings = 0;
  private _renderWindowStartMs = 0;
  private _renderWindowCount = 0;

  recordProjection(rowCount: number, durationMs: number): void {
    this._projectionRebuilds += 1;
    this._rowsProjectedTotal += rowCount;
    if (Number.isFinite(durationMs) && durationMs >= 0) {
      this._lastProjectionMs = durationMs;
      if (durationMs > this._maxProjectionMs) this._maxProjectionMs = durationMs;
    }
  }

  recordPipeline(durationMs: number): void {
    this._pipelineRuns += 1;
    if (Number.isFinite(durationMs) && durationMs >= 0) {
      this._lastPipelineMs = durationMs;
      if (durationMs > this._maxPipelineMs) this._maxPipelineMs = durationMs;
    }
  }

  recordFilterEvaluation(): void {
    this._filterEvaluations += 1;
  }

  recordGroupRebuild(): void {
    this._groupRebuilds += 1;
  }

  recordRowRender(): void {
    this._rowRenders += 1;
    const now = typeof performance !== "undefined" ? performance.now() : Date.now();
    if (now - this._renderWindowStartMs > 1000) {
      this._renderWindowStartMs = now;
      this._renderWindowCount = 1;
      return;
    }
    this._renderWindowCount += 1;
    if (this._renderWindowCount > RENDER_STORM_THRESHOLD) {
      this._renderStormWarnings += 1;
      this._renderWindowStartMs = now;
      this._renderWindowCount = 0;
    }
  }

  recordLiveAppend(count: number = 1): void {
    this._liveAppends += count;
  }

  recordReplayAppend(count: number = 1): void {
    this._replayAppends += count;
  }

  snapshot(): EventFeedMetricsSnapshot {
    return {
      projectionRebuilds: this._projectionRebuilds,
      pipelineRuns: this._pipelineRuns,
      rowRenders: this._rowRenders,
      groupRebuilds: this._groupRebuilds,
      filterEvaluations: this._filterEvaluations,
      liveAppends: this._liveAppends,
      replayAppends: this._replayAppends,
      rowsProjectedTotal: this._rowsProjectedTotal,
      lastPipelineMs: this._lastPipelineMs,
      maxPipelineMs: this._maxPipelineMs,
      lastProjectionMs: this._lastProjectionMs,
      maxProjectionMs: this._maxProjectionMs,
      renderStormWarnings: this._renderStormWarnings,
    };
  }

  reset(): void {
    this._projectionRebuilds = 0;
    this._pipelineRuns = 0;
    this._rowRenders = 0;
    this._groupRebuilds = 0;
    this._filterEvaluations = 0;
    this._liveAppends = 0;
    this._replayAppends = 0;
    this._rowsProjectedTotal = 0;
    this._lastPipelineMs = 0;
    this._maxPipelineMs = 0;
    this._lastProjectionMs = 0;
    this._maxProjectionMs = 0;
    this._renderStormWarnings = 0;
    this._renderWindowStartMs = 0;
    this._renderWindowCount = 0;
  }
}

let _instance: EventFeedMetrics | null = null;

export function getEventFeedMetrics(): EventFeedMetrics {
  if (_instance === null) _instance = new EventFeedMetrics();
  return _instance;
}

export function resetEventFeedMetrics(): void {
  if (_instance !== null) _instance.reset();
}
