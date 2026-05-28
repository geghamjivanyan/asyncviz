/**
 * Observability counters for the live task table.
 *
 * Mirrors the pattern set by :class:`ClientMetrics` — one class per
 * subsystem, frozen snapshot view, no module-level singletons. The
 * instance is owned by :func:`useTaskTableMetrics`; tests can
 * construct their own and assert on it directly.
 */

export interface TaskTableMetricsSnapshot {
  /** Number of row-projection rebuilds (memo-input churn). */
  projectionRebuilds: number;
  /** Number of selector evaluations the table has triggered. */
  selectorEvaluations: number;
  /** Number of filter/sort pipeline runs. */
  pipelineRuns: number;
  /** Number of row-component renders. */
  rowRenders: number;
  /** Number of selection events. */
  selectionEvents: number;
  /** Number of times the table emitted a render-storm warning (>N renders/s). */
  renderStormWarnings: number;
  /** Total rows projected across the lifetime of the instance. */
  rowsProjectedTotal: number;
  /** Last observed pipeline duration in ms. */
  lastPipelineMs: number;
  /** Max observed pipeline duration in ms. */
  maxPipelineMs: number;
  /** Last observed projection duration in ms. */
  lastProjectionMs: number;
  /** Max observed projection duration in ms. */
  maxProjectionMs: number;
}

const RENDER_STORM_THRESHOLD = 60;

export class TaskTableMetrics {
  private _projectionRebuilds = 0;
  private _selectorEvaluations = 0;
  private _pipelineRuns = 0;
  private _rowRenders = 0;
  private _selectionEvents = 0;
  private _renderStormWarnings = 0;
  private _rowsProjectedTotal = 0;
  private _lastPipelineMs = 0;
  private _maxPipelineMs = 0;
  private _lastProjectionMs = 0;
  private _maxProjectionMs = 0;
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

  recordSelectorEvaluation(): void {
    this._selectorEvaluations += 1;
  }

  recordPipeline(durationMs: number): void {
    this._pipelineRuns += 1;
    if (Number.isFinite(durationMs) && durationMs >= 0) {
      this._lastPipelineMs = durationMs;
      if (durationMs > this._maxPipelineMs) this._maxPipelineMs = durationMs;
    }
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

  recordSelection(): void {
    this._selectionEvents += 1;
  }

  snapshot(): TaskTableMetricsSnapshot {
    return {
      projectionRebuilds: this._projectionRebuilds,
      selectorEvaluations: this._selectorEvaluations,
      pipelineRuns: this._pipelineRuns,
      rowRenders: this._rowRenders,
      selectionEvents: this._selectionEvents,
      renderStormWarnings: this._renderStormWarnings,
      rowsProjectedTotal: this._rowsProjectedTotal,
      lastPipelineMs: this._lastPipelineMs,
      maxPipelineMs: this._maxPipelineMs,
      lastProjectionMs: this._lastProjectionMs,
      maxProjectionMs: this._maxProjectionMs,
    };
  }

  reset(): void {
    this._projectionRebuilds = 0;
    this._selectorEvaluations = 0;
    this._pipelineRuns = 0;
    this._rowRenders = 0;
    this._selectionEvents = 0;
    this._renderStormWarnings = 0;
    this._rowsProjectedTotal = 0;
    this._lastPipelineMs = 0;
    this._maxPipelineMs = 0;
    this._lastProjectionMs = 0;
    this._maxProjectionMs = 0;
    this._renderWindowStartMs = 0;
    this._renderWindowCount = 0;
  }
}

let _instance: TaskTableMetrics | null = null;

/** Shared instance used by the table runtime. Tests can call
 *  :func:`resetTaskTableMetrics` before each case. */
export function getTaskTableMetrics(): TaskTableMetrics {
  if (_instance === null) {
    _instance = new TaskTableMetrics();
  }
  return _instance;
}

export function resetTaskTableMetrics(): void {
  if (_instance !== null) _instance.reset();
}
