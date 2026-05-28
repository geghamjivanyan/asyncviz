/**
 * Observability counters for the canonical pan controller.
 */

import type { PanReason } from "@/dashboard/timeline/pan/models/TimelinePanModels";

export interface TimelinePanMetricsSnapshot {
  pansApplied: number;
  pansByReason: Record<PanReason, number>;
  totalSecondsPanned: number;
  totalAbsSecondsPanned: number;
  dragsStarted: number;
  dragsCompleted: number;
  dragsCancelled: number;
  dragSecondsTotal: number;
  dragLongestMs: number;
  wheelGestures: number;
  keyboardSteps: number;
  centerCalls: number;
  panToTimeCalls: number;
  constraintHitsMin: number;
  constraintHitsMax: number;
  noopsSuppressed: number;
  lastPanLatencyMs: number;
  maxPanLatencyMs: number;
  totalPanLatencyMs: number;
}

function emptyReasons(): Record<PanReason, number> {
  return {
    drag: 0,
    wheel: 0,
    keyboard: 0,
    center: 0,
    "to-time": 0,
    manual: 0,
    inertial: 0,
  };
}

export class TimelinePanMetrics {
  private _pansApplied = 0;
  private _pansByReason: Record<PanReason, number> = emptyReasons();
  private _totalSecondsPanned = 0;
  private _totalAbsSecondsPanned = 0;
  private _dragsStarted = 0;
  private _dragsCompleted = 0;
  private _dragsCancelled = 0;
  private _dragSecondsTotal = 0;
  private _dragLongestMs = 0;
  private _wheelGestures = 0;
  private _keyboardSteps = 0;
  private _centerCalls = 0;
  private _panToTimeCalls = 0;
  private _constraintHitsMin = 0;
  private _constraintHitsMax = 0;
  private _noopsSuppressed = 0;
  private _lastPanLatencyMs = 0;
  private _maxPanLatencyMs = 0;
  private _totalPanLatencyMs = 0;

  recordPan(reason: PanReason, deltaSeconds: number): void {
    this._pansApplied += 1;
    this._pansByReason[reason] = (this._pansByReason[reason] ?? 0) + 1;
    if (Number.isFinite(deltaSeconds)) {
      this._totalSecondsPanned += deltaSeconds;
      this._totalAbsSecondsPanned += Math.abs(deltaSeconds);
    }
  }

  recordDragStart(): void {
    this._dragsStarted += 1;
  }

  recordDragComplete(args: { durationMs: number; secondsMoved: number }): void {
    this._dragsCompleted += 1;
    if (Number.isFinite(args.durationMs) && args.durationMs > this._dragLongestMs) {
      this._dragLongestMs = args.durationMs;
    }
    if (Number.isFinite(args.secondsMoved)) {
      this._dragSecondsTotal += Math.abs(args.secondsMoved);
    }
  }

  recordDragCancel(): void {
    this._dragsCancelled += 1;
  }

  recordWheel(): void {
    this._wheelGestures += 1;
  }

  recordKeyboard(): void {
    this._keyboardSteps += 1;
  }

  recordCenter(): void {
    this._centerCalls += 1;
  }

  recordPanToTime(): void {
    this._panToTimeCalls += 1;
  }

  recordConstraintHit(edge: "min" | "max"): void {
    if (edge === "min") this._constraintHitsMin += 1;
    else this._constraintHitsMax += 1;
  }

  recordNoopSuppressed(): void {
    this._noopsSuppressed += 1;
  }

  recordPanLatency(durationMs: number): void {
    if (!Number.isFinite(durationMs) || durationMs < 0) return;
    this._totalPanLatencyMs += durationMs;
    this._lastPanLatencyMs = durationMs;
    if (durationMs > this._maxPanLatencyMs) this._maxPanLatencyMs = durationMs;
  }

  snapshot(): TimelinePanMetricsSnapshot {
    return {
      pansApplied: this._pansApplied,
      pansByReason: { ...this._pansByReason },
      totalSecondsPanned: this._totalSecondsPanned,
      totalAbsSecondsPanned: this._totalAbsSecondsPanned,
      dragsStarted: this._dragsStarted,
      dragsCompleted: this._dragsCompleted,
      dragsCancelled: this._dragsCancelled,
      dragSecondsTotal: this._dragSecondsTotal,
      dragLongestMs: this._dragLongestMs,
      wheelGestures: this._wheelGestures,
      keyboardSteps: this._keyboardSteps,
      centerCalls: this._centerCalls,
      panToTimeCalls: this._panToTimeCalls,
      constraintHitsMin: this._constraintHitsMin,
      constraintHitsMax: this._constraintHitsMax,
      noopsSuppressed: this._noopsSuppressed,
      lastPanLatencyMs: this._lastPanLatencyMs,
      maxPanLatencyMs: this._maxPanLatencyMs,
      totalPanLatencyMs: this._totalPanLatencyMs,
    };
  }

  reset(): void {
    this._pansApplied = 0;
    this._pansByReason = emptyReasons();
    this._totalSecondsPanned = 0;
    this._totalAbsSecondsPanned = 0;
    this._dragsStarted = 0;
    this._dragsCompleted = 0;
    this._dragsCancelled = 0;
    this._dragSecondsTotal = 0;
    this._dragLongestMs = 0;
    this._wheelGestures = 0;
    this._keyboardSteps = 0;
    this._centerCalls = 0;
    this._panToTimeCalls = 0;
    this._constraintHitsMin = 0;
    this._constraintHitsMax = 0;
    this._noopsSuppressed = 0;
    this._lastPanLatencyMs = 0;
    this._maxPanLatencyMs = 0;
    this._totalPanLatencyMs = 0;
  }
}

let _instance: TimelinePanMetrics | null = null;

export function getTimelinePanMetrics(): TimelinePanMetrics {
  if (_instance === null) _instance = new TimelinePanMetrics();
  return _instance;
}

export function resetTimelinePanMetrics(): void {
  if (_instance !== null) _instance.reset();
}
