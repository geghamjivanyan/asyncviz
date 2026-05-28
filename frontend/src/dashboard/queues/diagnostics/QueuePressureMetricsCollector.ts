/**
 * Frontend-side observability counters for the queue pressure panel.
 *
 * Mirrors the existing ``BlockingWarningMetricsCollector`` pattern —
 * a process-wide singleton with thread-safe bumps + a frozen snapshot
 * type. The diagnostics page reads from here.
 */

export interface QueuePressurePanelMetricsSnapshot {
  hydrations: number;
  hydrationFailures: number;
  websocketEvents: number;
  markersRendered: number;
  cardsRendered: number;
  selectionChanges: number;
  inspectorReveals: number;
}

class QueuePressurePanelMetrics {
  private _hydrations = 0;
  private _hydrationFailures = 0;
  private _websocketEvents = 0;
  private _markersRendered = 0;
  private _cardsRendered = 0;
  private _selectionChanges = 0;
  private _inspectorReveals = 0;

  recordHydration(): void {
    this._hydrations += 1;
  }

  recordHydrationFailure(): void {
    this._hydrationFailures += 1;
  }

  recordWebsocketEvent(): void {
    this._websocketEvents += 1;
  }

  recordMarkersRendered(count: number): void {
    if (count > 0) this._markersRendered += count;
  }

  recordCardsRendered(count: number): void {
    if (count > 0) this._cardsRendered += count;
  }

  recordSelectionChange(): void {
    this._selectionChanges += 1;
  }

  recordInspectorReveal(): void {
    this._inspectorReveals += 1;
  }

  snapshot(): QueuePressurePanelMetricsSnapshot {
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

const _instance = new QueuePressurePanelMetrics();

export function getQueuePressurePanelMetrics(): QueuePressurePanelMetrics {
  return _instance;
}

export function resetQueuePressurePanelMetrics(): void {
  _instance.reset();
}
