/**
 * Observability counters for the canonical selection controller.
 */

import type { SelectionReason } from "@/dashboard/timeline/selection/models/TimelineSelectionModels";

export interface TimelineSelectionMetricsSnapshot {
  selectionChanges: number;
  selectionsByReason: Record<SelectionReason, number>;
  pointerSelects: number;
  keyboardSelects: number;
  programmaticSelects: number;
  clears: number;
  navigateNext: number;
  navigatePrev: number;
  navigateHome: number;
  navigateEnd: number;
  centerOnSelectionCalls: number;
  revealCalls: number;
  noopsSuppressed: number;
  restoreCalls: number;
  restoreMisses: number;
  lastChangeLatencyMs: number;
  maxChangeLatencyMs: number;
  totalChangeLatencyMs: number;
}

function emptyReasons(): Record<SelectionReason, number> {
  return {
    pointer: 0,
    keyboard: 0,
    programmatic: 0,
    restore: 0,
    store: 0,
    clear: 0,
  };
}

export class TimelineSelectionMetrics {
  private _selectionChanges = 0;
  private _selectionsByReason: Record<SelectionReason, number> = emptyReasons();
  private _pointerSelects = 0;
  private _keyboardSelects = 0;
  private _programmaticSelects = 0;
  private _clears = 0;
  private _navigateNext = 0;
  private _navigatePrev = 0;
  private _navigateHome = 0;
  private _navigateEnd = 0;
  private _centerOnSelectionCalls = 0;
  private _revealCalls = 0;
  private _noopsSuppressed = 0;
  private _restoreCalls = 0;
  private _restoreMisses = 0;
  private _lastChangeLatencyMs = 0;
  private _maxChangeLatencyMs = 0;
  private _totalChangeLatencyMs = 0;

  recordSelectionChange(reason: SelectionReason): void {
    this._selectionChanges += 1;
    this._selectionsByReason[reason] = (this._selectionsByReason[reason] ?? 0) + 1;
    if (reason === "pointer") this._pointerSelects += 1;
    else if (reason === "keyboard") this._keyboardSelects += 1;
    else if (reason === "programmatic") this._programmaticSelects += 1;
    else if (reason === "clear") this._clears += 1;
  }

  recordNavigation(kind: "next" | "prev" | "home" | "end"): void {
    if (kind === "next") this._navigateNext += 1;
    else if (kind === "prev") this._navigatePrev += 1;
    else if (kind === "home") this._navigateHome += 1;
    else this._navigateEnd += 1;
  }

  recordCenter(): void {
    this._centerOnSelectionCalls += 1;
  }

  recordReveal(): void {
    this._revealCalls += 1;
  }

  recordNoopSuppressed(): void {
    this._noopsSuppressed += 1;
  }

  recordRestore(hit: boolean): void {
    this._restoreCalls += 1;
    if (!hit) this._restoreMisses += 1;
  }

  recordChangeLatency(durationMs: number): void {
    if (!Number.isFinite(durationMs) || durationMs < 0) return;
    this._totalChangeLatencyMs += durationMs;
    this._lastChangeLatencyMs = durationMs;
    if (durationMs > this._maxChangeLatencyMs) this._maxChangeLatencyMs = durationMs;
  }

  snapshot(): TimelineSelectionMetricsSnapshot {
    return {
      selectionChanges: this._selectionChanges,
      selectionsByReason: { ...this._selectionsByReason },
      pointerSelects: this._pointerSelects,
      keyboardSelects: this._keyboardSelects,
      programmaticSelects: this._programmaticSelects,
      clears: this._clears,
      navigateNext: this._navigateNext,
      navigatePrev: this._navigatePrev,
      navigateHome: this._navigateHome,
      navigateEnd: this._navigateEnd,
      centerOnSelectionCalls: this._centerOnSelectionCalls,
      revealCalls: this._revealCalls,
      noopsSuppressed: this._noopsSuppressed,
      restoreCalls: this._restoreCalls,
      restoreMisses: this._restoreMisses,
      lastChangeLatencyMs: this._lastChangeLatencyMs,
      maxChangeLatencyMs: this._maxChangeLatencyMs,
      totalChangeLatencyMs: this._totalChangeLatencyMs,
    };
  }

  reset(): void {
    this._selectionChanges = 0;
    this._selectionsByReason = emptyReasons();
    this._pointerSelects = 0;
    this._keyboardSelects = 0;
    this._programmaticSelects = 0;
    this._clears = 0;
    this._navigateNext = 0;
    this._navigatePrev = 0;
    this._navigateHome = 0;
    this._navigateEnd = 0;
    this._centerOnSelectionCalls = 0;
    this._revealCalls = 0;
    this._noopsSuppressed = 0;
    this._restoreCalls = 0;
    this._restoreMisses = 0;
    this._lastChangeLatencyMs = 0;
    this._maxChangeLatencyMs = 0;
    this._totalChangeLatencyMs = 0;
  }
}

let _instance: TimelineSelectionMetrics | null = null;

export function getTimelineSelectionMetrics(): TimelineSelectionMetrics {
  if (_instance === null) _instance = new TimelineSelectionMetrics();
  return _instance;
}

export function resetTimelineSelectionMetrics(): void {
  if (_instance !== null) _instance.reset();
}
