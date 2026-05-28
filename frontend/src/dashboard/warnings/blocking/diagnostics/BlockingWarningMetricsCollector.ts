/**
 * Per-panel observability counters.
 *
 * Distinct from :class:`ClientMetrics` (process-wide) — this collector
 * is scoped to the blocking-warning panel and exposed via
 * :func:`getBlockingWarningPanelMetrics` for the diagnostics surface.
 *
 * The instance is module-scoped (singleton) because the panel has at
 * most one live mount at a time and the React tree doesn't need to
 * thread the collector through props. Tests reach in via
 * :func:`resetBlockingWarningPanelMetrics`.
 */

export interface BlockingWarningPanelMetricsSnapshot {
  hydrationCount: number;
  hydrationFailures: number;
  liveEventsApplied: number;
  liveEventsDropped: number;
  filterChanges: number;
  selectionChanges: number;
  /** Last few render-duration samples (bounded ring). */
  recentRenderDurationsMs: readonly number[];
  /** Max observed render duration, ms. */
  maxRenderDurationMs: number;
  /** Avg observed render duration, ms. */
  averageRenderDurationMs: number;
  lastEventAtMs: number;
}

const SAMPLE_RING_CAPACITY = 16;

class BlockingWarningPanelMetrics {
  private _hydrationCount = 0;
  private _hydrationFailures = 0;
  private _liveEventsApplied = 0;
  private _liveEventsDropped = 0;
  private _filterChanges = 0;
  private _selectionChanges = 0;
  private _renderSamples: number[] = [];
  private _maxRender = 0;
  private _totalRender = 0;
  private _lastEventAtMs = 0;

  recordHydration(): void {
    this._hydrationCount += 1;
  }

  recordHydrationFailure(): void {
    this._hydrationFailures += 1;
  }

  recordLiveEvent(): void {
    this._liveEventsApplied += 1;
    this._lastEventAtMs = typeof performance !== "undefined" ? performance.now() : Date.now();
  }

  recordLiveEventDropped(): void {
    this._liveEventsDropped += 1;
  }

  recordFilterChange(): void {
    this._filterChanges += 1;
  }

  recordSelectionChange(): void {
    this._selectionChanges += 1;
  }

  recordRenderDuration(durationMs: number): void {
    if (!Number.isFinite(durationMs) || durationMs < 0) return;
    this._totalRender += durationMs;
    if (durationMs > this._maxRender) this._maxRender = durationMs;
    this._renderSamples.push(durationMs);
    if (this._renderSamples.length > SAMPLE_RING_CAPACITY) {
      this._renderSamples.shift();
    }
  }

  snapshot(): BlockingWarningPanelMetricsSnapshot {
    const count = this._renderSamples.length;
    const avg = count === 0 ? 0 : this._totalRender / count;
    return {
      hydrationCount: this._hydrationCount,
      hydrationFailures: this._hydrationFailures,
      liveEventsApplied: this._liveEventsApplied,
      liveEventsDropped: this._liveEventsDropped,
      filterChanges: this._filterChanges,
      selectionChanges: this._selectionChanges,
      recentRenderDurationsMs: [...this._renderSamples],
      maxRenderDurationMs: this._maxRender,
      averageRenderDurationMs: avg,
      lastEventAtMs: this._lastEventAtMs,
    };
  }

  reset(): void {
    this._hydrationCount = 0;
    this._hydrationFailures = 0;
    this._liveEventsApplied = 0;
    this._liveEventsDropped = 0;
    this._filterChanges = 0;
    this._selectionChanges = 0;
    this._renderSamples = [];
    this._maxRender = 0;
    this._totalRender = 0;
    this._lastEventAtMs = 0;
  }
}

const _instance = new BlockingWarningPanelMetrics();

export function getBlockingWarningPanelMetrics(): BlockingWarningPanelMetrics {
  return _instance;
}

export function resetBlockingWarningPanelMetrics(): void {
  _instance.reset();
}
