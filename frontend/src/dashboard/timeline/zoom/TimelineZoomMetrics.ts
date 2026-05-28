/**
 * Observability counters for the canonical zoom controller.
 */

export interface TimelineZoomMetricsSnapshot {
  zoomIns: number;
  zoomOuts: number;
  zoomFits: number;
  zoomSetLevels: number;
  zoomByFactor: number;
  presetActivations: number;
  shortcutInvocations: number;
  wheelGestures: number;
  pinchGestures: number;
  constraintHitsMin: number;
  constraintHitsMax: number;
  noopsSuppressed: number;
  lastZoomLatencyMs: number;
  maxZoomLatencyMs: number;
  totalZoomLatencyMs: number;
  fitsByKind: Record<string, number>;
}

export class TimelineZoomMetrics {
  private _zoomIns = 0;
  private _zoomOuts = 0;
  private _zoomFits = 0;
  private _zoomSetLevels = 0;
  private _zoomByFactor = 0;
  private _presetActivations = 0;
  private _shortcutInvocations = 0;
  private _wheelGestures = 0;
  private _pinchGestures = 0;
  private _constraintHitsMin = 0;
  private _constraintHitsMax = 0;
  private _noopsSuppressed = 0;
  private _lastZoomLatencyMs = 0;
  private _maxZoomLatencyMs = 0;
  private _totalZoomLatencyMs = 0;
  private _fitsByKind: Record<string, number> = {};

  recordZoomIn(): void {
    this._zoomIns += 1;
  }

  recordZoomOut(): void {
    this._zoomOuts += 1;
  }

  recordZoomFit(kind: string): void {
    this._zoomFits += 1;
    this._fitsByKind[kind] = (this._fitsByKind[kind] ?? 0) + 1;
  }

  recordZoomSetLevel(): void {
    this._zoomSetLevels += 1;
  }

  recordZoomByFactor(): void {
    this._zoomByFactor += 1;
  }

  recordPresetActivation(): void {
    this._presetActivations += 1;
  }

  recordShortcut(): void {
    this._shortcutInvocations += 1;
  }

  recordWheel(): void {
    this._wheelGestures += 1;
  }

  recordPinch(): void {
    this._pinchGestures += 1;
  }

  recordConstraintHit(edge: "min" | "max"): void {
    if (edge === "min") this._constraintHitsMin += 1;
    else this._constraintHitsMax += 1;
  }

  recordNoopSuppressed(): void {
    this._noopsSuppressed += 1;
  }

  recordZoomLatency(durationMs: number): void {
    if (!Number.isFinite(durationMs) || durationMs < 0) return;
    this._totalZoomLatencyMs += durationMs;
    this._lastZoomLatencyMs = durationMs;
    if (durationMs > this._maxZoomLatencyMs) this._maxZoomLatencyMs = durationMs;
  }

  snapshot(): TimelineZoomMetricsSnapshot {
    return {
      zoomIns: this._zoomIns,
      zoomOuts: this._zoomOuts,
      zoomFits: this._zoomFits,
      zoomSetLevels: this._zoomSetLevels,
      zoomByFactor: this._zoomByFactor,
      presetActivations: this._presetActivations,
      shortcutInvocations: this._shortcutInvocations,
      wheelGestures: this._wheelGestures,
      pinchGestures: this._pinchGestures,
      constraintHitsMin: this._constraintHitsMin,
      constraintHitsMax: this._constraintHitsMax,
      noopsSuppressed: this._noopsSuppressed,
      lastZoomLatencyMs: this._lastZoomLatencyMs,
      maxZoomLatencyMs: this._maxZoomLatencyMs,
      totalZoomLatencyMs: this._totalZoomLatencyMs,
      fitsByKind: { ...this._fitsByKind },
    };
  }

  reset(): void {
    this._zoomIns = 0;
    this._zoomOuts = 0;
    this._zoomFits = 0;
    this._zoomSetLevels = 0;
    this._zoomByFactor = 0;
    this._presetActivations = 0;
    this._shortcutInvocations = 0;
    this._wheelGestures = 0;
    this._pinchGestures = 0;
    this._constraintHitsMin = 0;
    this._constraintHitsMax = 0;
    this._noopsSuppressed = 0;
    this._lastZoomLatencyMs = 0;
    this._maxZoomLatencyMs = 0;
    this._totalZoomLatencyMs = 0;
    this._fitsByKind = {};
  }
}

let _instance: TimelineZoomMetrics | null = null;

export function getTimelineZoomMetrics(): TimelineZoomMetrics {
  if (_instance === null) _instance = new TimelineZoomMetrics();
  return _instance;
}

export function resetTimelineZoomMetrics(): void {
  if (_instance !== null) _instance.reset();
}
