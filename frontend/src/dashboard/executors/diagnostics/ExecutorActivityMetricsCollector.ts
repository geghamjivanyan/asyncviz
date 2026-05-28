/**
 * Frontend-side observability counters for the executor activity panel.
 */

export interface ExecutorActivityPanelMetricsSnapshot {
  hydrations: number;
  hydrationFailures: number;
  websocketEvents: number;
  markersRendered: number;
  cardsRendered: number;
  selectionChanges: number;
  inspectorReveals: number;
}

class ExecutorActivityPanelMetrics {
  private _hydrations = 0;
  private _hydrationFailures = 0;
  private _websocketEvents = 0;
  private _markersRendered = 0;
  private _cardsRendered = 0;
  private _selectionChanges = 0;
  private _inspectorReveals = 0;

  recordHydration(): void { this._hydrations += 1; }
  recordHydrationFailure(): void { this._hydrationFailures += 1; }
  recordWebsocketEvent(): void { this._websocketEvents += 1; }
  recordMarkersRendered(n: number): void { if (n > 0) this._markersRendered += n; }
  recordCardsRendered(n: number): void { if (n > 0) this._cardsRendered += n; }
  recordSelectionChange(): void { this._selectionChanges += 1; }
  recordInspectorReveal(): void { this._inspectorReveals += 1; }

  snapshot(): ExecutorActivityPanelMetricsSnapshot {
    return {
      hydrations: this._hydrations,
      hydrationFailures: this._hydrationFailures,
      websocketEvents: this._websocketEvents,
      markersRendered: this._markersRendered,
      cardsRendered: this._cardsRendered,
      selectionChanges: this._selectionChanges,
      inspectorReveals: this._inspectorReveals,
    };
  }

  reset(): void {
    this._hydrations = 0;
    this._hydrationFailures = 0;
    this._websocketEvents = 0;
    this._markersRendered = 0;
    this._cardsRendered = 0;
    this._selectionChanges = 0;
    this._inspectorReveals = 0;
  }
}

const _instance = new ExecutorActivityPanelMetrics();

export function getExecutorActivityPanelMetrics(): ExecutorActivityPanelMetrics {
  return _instance;
}

export function resetExecutorActivityPanelMetrics(): void {
  _instance.reset();
}
