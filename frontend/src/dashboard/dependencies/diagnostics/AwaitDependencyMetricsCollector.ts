/**
 * Frontend-side observability counters for the dependency graph.
 *
 * Singleton — diagnostics page polls ``snapshot()``.
 */

export interface AwaitDependencyMetricsSnapshot {
  websocketEvents: number;
  framesRendered: number;
  nodesRendered: number;
  edgesRendered: number;
  layoutsComputed: number;
  selectionChanges: number;
  inspectorReveals: number;
}

class AwaitDependencyPanelMetrics {
  private _websocketEvents = 0;
  private _framesRendered = 0;
  private _nodesRendered = 0;
  private _edgesRendered = 0;
  private _layoutsComputed = 0;
  private _selectionChanges = 0;
  private _inspectorReveals = 0;

  recordWebsocketEvent(): void {
    this._websocketEvents += 1;
  }
  recordFrameRendered(): void {
    this._framesRendered += 1;
  }
  recordNodesRendered(n: number): void {
    if (n > 0) this._nodesRendered += n;
  }
  recordEdgesRendered(n: number): void {
    if (n > 0) this._edgesRendered += n;
  }
  recordLayoutComputed(): void {
    this._layoutsComputed += 1;
  }
  recordSelectionChange(): void {
    this._selectionChanges += 1;
  }
  recordInspectorReveal(): void {
    this._inspectorReveals += 1;
  }

  snapshot(): AwaitDependencyMetricsSnapshot {
    return {
      websocketEvents: this._websocketEvents,
      framesRendered: this._framesRendered,
      nodesRendered: this._nodesRendered,
      edgesRendered: this._edgesRendered,
      layoutsComputed: this._layoutsComputed,
      selectionChanges: this._selectionChanges,
      inspectorReveals: this._inspectorReveals,
    };
  }

  reset(): void {
    this._websocketEvents = 0;
    this._framesRendered = 0;
    this._nodesRendered = 0;
    this._edgesRendered = 0;
    this._layoutsComputed = 0;
    this._selectionChanges = 0;
    this._inspectorReveals = 0;
  }
}

const _instance = new AwaitDependencyPanelMetrics();

export function getAwaitDependencyPanelMetrics(): AwaitDependencyPanelMetrics {
  return _instance;
}

export function resetAwaitDependencyPanelMetrics(): void {
  _instance.reset();
}
