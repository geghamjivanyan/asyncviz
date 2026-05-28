/**
 * Observability counters for the canonical task-detail inspector.
 */

import type { InspectorPanelKind } from "@/dashboard/inspector/models/TaskInspectionModels";

export interface TaskInspectorMetricsSnapshot {
  inspectionsBuilt: number;
  totalProjectionMs: number;
  lastProjectionMs: number;
  maxProjectionMs: number;
  panelsRendered: number;
  panelRendersByKind: Record<InspectorPanelKind, number>;
  panelSwitches: number;
  revealCalls: number;
  fitCalls: number;
  warningCorrelations: number;
  emptyStateRenders: number;
  loadingStateRenders: number;
  selectionRebuilds: number;
}

function emptyPanelRenders(): Record<InspectorPanelKind, number> {
  return {
    overview: 0,
    timeline: 0,
    metrics: 0,
    warnings: 0,
    relationships: 0,
    events: 0,
    replay: 0,
    lifecycle: 0,
    metadata: 0,
    diagnostics: 0,
  };
}

export class TaskInspectorMetrics {
  private _inspectionsBuilt = 0;
  private _totalProjectionMs = 0;
  private _lastProjectionMs = 0;
  private _maxProjectionMs = 0;
  private _panelsRendered = 0;
  private _panelRendersByKind: Record<InspectorPanelKind, number> = emptyPanelRenders();
  private _panelSwitches = 0;
  private _revealCalls = 0;
  private _fitCalls = 0;
  private _warningCorrelations = 0;
  private _emptyStateRenders = 0;
  private _loadingStateRenders = 0;
  private _selectionRebuilds = 0;

  recordProjection(durationMs: number): void {
    this._inspectionsBuilt += 1;
    if (!Number.isFinite(durationMs) || durationMs < 0) return;
    this._totalProjectionMs += durationMs;
    this._lastProjectionMs = durationMs;
    if (durationMs > this._maxProjectionMs) this._maxProjectionMs = durationMs;
  }

  recordPanelRender(kind: InspectorPanelKind): void {
    this._panelsRendered += 1;
    this._panelRendersByKind[kind] = (this._panelRendersByKind[kind] ?? 0) + 1;
  }

  recordPanelSwitch(): void {
    this._panelSwitches += 1;
  }

  recordReveal(): void {
    this._revealCalls += 1;
  }

  recordFit(): void {
    this._fitCalls += 1;
  }

  recordWarningCorrelation(count: number): void {
    if (count > 0) this._warningCorrelations += count;
  }

  recordEmptyState(): void {
    this._emptyStateRenders += 1;
  }

  recordLoadingState(): void {
    this._loadingStateRenders += 1;
  }

  recordSelectionRebuild(): void {
    this._selectionRebuilds += 1;
  }

  snapshot(): TaskInspectorMetricsSnapshot {
    return {
      inspectionsBuilt: this._inspectionsBuilt,
      totalProjectionMs: this._totalProjectionMs,
      lastProjectionMs: this._lastProjectionMs,
      maxProjectionMs: this._maxProjectionMs,
      panelsRendered: this._panelsRendered,
      panelRendersByKind: { ...this._panelRendersByKind },
      panelSwitches: this._panelSwitches,
      revealCalls: this._revealCalls,
      fitCalls: this._fitCalls,
      warningCorrelations: this._warningCorrelations,
      emptyStateRenders: this._emptyStateRenders,
      loadingStateRenders: this._loadingStateRenders,
      selectionRebuilds: this._selectionRebuilds,
    };
  }

  reset(): void {
    this._inspectionsBuilt = 0;
    this._totalProjectionMs = 0;
    this._lastProjectionMs = 0;
    this._maxProjectionMs = 0;
    this._panelsRendered = 0;
    this._panelRendersByKind = emptyPanelRenders();
    this._panelSwitches = 0;
    this._revealCalls = 0;
    this._fitCalls = 0;
    this._warningCorrelations = 0;
    this._emptyStateRenders = 0;
    this._loadingStateRenders = 0;
    this._selectionRebuilds = 0;
  }
}

let _instance: TaskInspectorMetrics | null = null;

export function getTimelineInspectorMetrics(): TaskInspectorMetrics {
  if (_instance === null) _instance = new TaskInspectorMetrics();
  return _instance;
}

export function resetTimelineInspectorMetrics(): void {
  if (_instance !== null) _instance.reset();
}
