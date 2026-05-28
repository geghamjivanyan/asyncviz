/**
 * Observability counters for the connection-status system.
 *
 * Mirrors the pattern set by the other modules: one class per
 * subsystem, frozen snapshot view, no module-level singletons in
 * tests. The shared instance returned by
 * :func:`getConnectionMetrics` is used by the live hooks.
 */

export interface ConnectionMetricsSnapshot {
  /** Projection rebuilds — fires every time selectors run. */
  projectionRebuilds: number;
  /** Phase transitions observed. */
  phaseTransitions: number;
  /** Replay transitions observed (live→replaying or vice versa). */
  replayTransitions: number;
  /** Hydrations started. */
  hydrationStarts: number;
  /** Hydrations completed. */
  hydrationCompletions: number;
  /** Reconnect attempts observed. */
  reconnectAttempts: number;
  /** Heartbeat stale detections. */
  heartbeatStaleDetections: number;
  /** Heartbeat offline detections. */
  heartbeatOfflineDetections: number;
  /** History entries appended. */
  historyAppends: number;
  /** Indicator render count. */
  indicatorRenders: number;
  /** Tooltip render count. */
  tooltipRenders: number;
  /** Last selector duration in ms. */
  lastSelectorMs: number;
  /** Max selector duration in ms. */
  maxSelectorMs: number;
  /** Render-storm warnings (>N renders/s). */
  renderStormWarnings: number;
}

const RENDER_STORM_THRESHOLD = 60;

export class ConnectionMetrics {
  private _projectionRebuilds = 0;
  private _phaseTransitions = 0;
  private _replayTransitions = 0;
  private _hydrationStarts = 0;
  private _hydrationCompletions = 0;
  private _reconnectAttempts = 0;
  private _heartbeatStaleDetections = 0;
  private _heartbeatOfflineDetections = 0;
  private _historyAppends = 0;
  private _indicatorRenders = 0;
  private _tooltipRenders = 0;
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

  recordPhaseTransition(): void {
    this._phaseTransitions += 1;
  }

  recordReplayTransition(): void {
    this._replayTransitions += 1;
  }

  recordHydrationStart(): void {
    this._hydrationStarts += 1;
  }

  recordHydrationCompletion(): void {
    this._hydrationCompletions += 1;
  }

  recordReconnectAttempt(): void {
    this._reconnectAttempts += 1;
  }

  recordHeartbeatStale(): void {
    this._heartbeatStaleDetections += 1;
  }

  recordHeartbeatOffline(): void {
    this._heartbeatOfflineDetections += 1;
  }

  recordHistoryAppend(): void {
    this._historyAppends += 1;
  }

  recordIndicatorRender(): void {
    this._indicatorRenders += 1;
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

  recordTooltipRender(): void {
    this._tooltipRenders += 1;
  }

  snapshot(): ConnectionMetricsSnapshot {
    return {
      projectionRebuilds: this._projectionRebuilds,
      phaseTransitions: this._phaseTransitions,
      replayTransitions: this._replayTransitions,
      hydrationStarts: this._hydrationStarts,
      hydrationCompletions: this._hydrationCompletions,
      reconnectAttempts: this._reconnectAttempts,
      heartbeatStaleDetections: this._heartbeatStaleDetections,
      heartbeatOfflineDetections: this._heartbeatOfflineDetections,
      historyAppends: this._historyAppends,
      indicatorRenders: this._indicatorRenders,
      tooltipRenders: this._tooltipRenders,
      lastSelectorMs: this._lastSelectorMs,
      maxSelectorMs: this._maxSelectorMs,
      renderStormWarnings: this._renderStormWarnings,
    };
  }

  reset(): void {
    this._projectionRebuilds = 0;
    this._phaseTransitions = 0;
    this._replayTransitions = 0;
    this._hydrationStarts = 0;
    this._hydrationCompletions = 0;
    this._reconnectAttempts = 0;
    this._heartbeatStaleDetections = 0;
    this._heartbeatOfflineDetections = 0;
    this._historyAppends = 0;
    this._indicatorRenders = 0;
    this._tooltipRenders = 0;
    this._lastSelectorMs = 0;
    this._maxSelectorMs = 0;
    this._renderStormWarnings = 0;
    this._renderWindowStartMs = 0;
    this._renderWindowCount = 0;
  }
}

let _instance: ConnectionMetrics | null = null;

export function getConnectionMetrics(): ConnectionMetrics {
  if (_instance === null) _instance = new ConnectionMetrics();
  return _instance;
}

export function resetConnectionMetrics(): void {
  if (_instance !== null) _instance.reset();
}
