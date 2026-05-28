/**
 * Observability counters for the metrics header.
 *
 * Mirrors the pattern set by :class:`ClientMetrics` /
 * :class:`TaskTableMetrics`: one class per subsystem, frozen snapshot
 * view, no module-level singletons. The shared instance returned by
 * :func:`getMetricsHeaderMetrics` is used by the live hooks; tests
 * call :func:`resetMetricsHeaderMetrics` between cases.
 */

export interface MetricsHeaderMetricsSnapshot {
  /** Projection rebuilds — increments every time selectors fire. */
  projectionRebuilds: number;
  /** Card render counts — diagnostic for low-rerender invariants. */
  cardRenders: number;
  /** Number of websocket phase transitions seen by the header. */
  phaseTransitions: number;
  /** Number of replay-state transitions observed. */
  replayTransitions: number;
  /** Number of warning aggregations recomputed. */
  warningAggregations: number;
  /** Number of throughput-tick samples folded into the rate tracker. */
  throughputSamples: number;
  /** Last selector-evaluation duration in ms. */
  lastSelectorMs: number;
  /** Max selector-evaluation duration in ms. */
  maxSelectorMs: number;
  /** Render-storm warnings (>N renders/s). */
  renderStormWarnings: number;
}

const RENDER_STORM_THRESHOLD = 90;

export class MetricsHeaderMetrics {
  private _projectionRebuilds = 0;
  private _cardRenders = 0;
  private _phaseTransitions = 0;
  private _replayTransitions = 0;
  private _warningAggregations = 0;
  private _throughputSamples = 0;
  private _lastSelectorMs = 0;
  private _maxSelectorMs = 0;
  private _renderStormWarnings = 0;
  private _renderWindowStartMs = 0;
  private _renderWindowCount = 0;

  recordProjection(durationMs: number): void {
    this._projectionRebuilds += 1;
    if (Number.isFinite(durationMs) && durationMs >= 0) {
      this._lastSelectorMs = durationMs;
      if (durationMs > this._maxSelectorMs) this._maxSelectorMs = durationMs;
    }
  }

  recordCardRender(): void {
    this._cardRenders += 1;
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

  recordPhaseTransition(): void {
    this._phaseTransitions += 1;
  }

  recordReplayTransition(): void {
    this._replayTransitions += 1;
  }

  recordWarningAggregation(): void {
    this._warningAggregations += 1;
  }

  recordThroughputSample(): void {
    this._throughputSamples += 1;
  }

  snapshot(): MetricsHeaderMetricsSnapshot {
    return {
      projectionRebuilds: this._projectionRebuilds,
      cardRenders: this._cardRenders,
      phaseTransitions: this._phaseTransitions,
      replayTransitions: this._replayTransitions,
      warningAggregations: this._warningAggregations,
      throughputSamples: this._throughputSamples,
      lastSelectorMs: this._lastSelectorMs,
      maxSelectorMs: this._maxSelectorMs,
      renderStormWarnings: this._renderStormWarnings,
    };
  }

  reset(): void {
    this._projectionRebuilds = 0;
    this._cardRenders = 0;
    this._phaseTransitions = 0;
    this._replayTransitions = 0;
    this._warningAggregations = 0;
    this._throughputSamples = 0;
    this._lastSelectorMs = 0;
    this._maxSelectorMs = 0;
    this._renderStormWarnings = 0;
    this._renderWindowStartMs = 0;
    this._renderWindowCount = 0;
  }
}

let _instance: MetricsHeaderMetrics | null = null;

export function getMetricsHeaderMetrics(): MetricsHeaderMetrics {
  if (_instance === null) {
    _instance = new MetricsHeaderMetrics();
  }
  return _instance;
}

export function resetMetricsHeaderMetrics(): void {
  if (_instance !== null) _instance.reset();
}
