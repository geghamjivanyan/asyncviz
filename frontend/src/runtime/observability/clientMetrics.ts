/**
 * Frontend-side observability counters.
 *
 * Mirrors the backend's pattern (one ``Metrics`` class per subsystem,
 * snapshot returns a frozen view) so the diagnostics panel can show
 * frontend + backend counters side-by-side without a parallel API.
 *
 * The instance is owned by ``RuntimeProvider`` and surfaced through
 * :func:`useClientMetrics`. No global singletons — tests construct a
 * fresh instance per render.
 */

export interface PanelMountSample {
  panelId: string;
  durationMs: number;
  recordedAtMs: number;
}

export interface NavigationSample {
  pathname: string;
  recordedAtMs: number;
}

export interface ClientMetricsSnapshot {
  websocketConnectAttempts: number;
  websocketReconnects: number;
  websocketFailures: number;
  envelopesReceived: number;
  envelopesDropped: number;
  protocolMismatches: number;
  snapshotHydrations: number;
  snapshotHydrationFailures: number;
  renderErrors: number;
  lastEnvelopeAtMonotonicMs: number;
  layoutPanelMounts: number;
  /** Last few panel-mount samples (bounded ring). */
  recentPanelMounts: readonly PanelMountSample[];
  /** Max observed panel-mount duration in ms. */
  maxPanelMountMs: number;
  /** Average mount duration across observed samples. */
  averagePanelMountMs: number;
  /** Total route navigation events recorded. */
  navigationsTotal: number;
  /** Last few navigation samples (bounded ring). */
  recentNavigations: readonly NavigationSample[];
  /** Number of layout observability errors (e.g. requestAnimationFrame unavailable). */
  layoutObservabilityErrors: number;
}

const SAMPLE_RING_CAPACITY = 16;

export class ClientMetrics {
  private _websocketConnectAttempts = 0;
  private _websocketReconnects = 0;
  private _websocketFailures = 0;
  private _envelopesReceived = 0;
  private _envelopesDropped = 0;
  private _protocolMismatches = 0;
  private _snapshotHydrations = 0;
  private _snapshotHydrationFailures = 0;
  private _renderErrors = 0;
  private _lastEnvelopeAtMonotonicMs = 0;
  private _layoutPanelMounts = 0;
  private _panelMountSamples: PanelMountSample[] = [];
  private _maxPanelMountMs = 0;
  private _totalPanelMountMs = 0;
  private _navigationsTotal = 0;
  private _navigationSamples: NavigationSample[] = [];
  private _layoutObservabilityErrors = 0;

  recordConnectAttempt(): void {
    this._websocketConnectAttempts += 1;
  }

  recordReconnect(): void {
    this._websocketReconnects += 1;
  }

  recordWebsocketFailure(): void {
    this._websocketFailures += 1;
  }

  recordEnvelope(): void {
    this._envelopesReceived += 1;
    this._lastEnvelopeAtMonotonicMs = performance.now();
  }

  recordEnvelopeDrop(): void {
    this._envelopesDropped += 1;
  }

  recordProtocolMismatch(): void {
    this._protocolMismatches += 1;
  }

  recordSnapshotHydration(): void {
    this._snapshotHydrations += 1;
  }

  recordSnapshotHydrationFailure(): void {
    this._snapshotHydrationFailures += 1;
  }

  recordRenderError(): void {
    this._renderErrors += 1;
  }

  recordPanelMount(panelId: string, durationMs: number): void {
    if (!Number.isFinite(durationMs) || durationMs < 0) {
      this._layoutObservabilityErrors += 1;
      return;
    }
    this._layoutPanelMounts += 1;
    this._totalPanelMountMs += durationMs;
    if (durationMs > this._maxPanelMountMs) {
      this._maxPanelMountMs = durationMs;
    }
    this._panelMountSamples.push({
      panelId,
      durationMs,
      recordedAtMs: performance.now(),
    });
    if (this._panelMountSamples.length > SAMPLE_RING_CAPACITY) {
      this._panelMountSamples.shift();
    }
  }

  recordNavigation(pathname: string): void {
    this._navigationsTotal += 1;
    this._navigationSamples.push({ pathname, recordedAtMs: performance.now() });
    if (this._navigationSamples.length > SAMPLE_RING_CAPACITY) {
      this._navigationSamples.shift();
    }
  }

  recordLayoutObservabilityError(): void {
    this._layoutObservabilityErrors += 1;
  }

  snapshot(): ClientMetricsSnapshot {
    const averagePanelMountMs =
      this._layoutPanelMounts === 0 ? 0 : this._totalPanelMountMs / this._layoutPanelMounts;
    return {
      websocketConnectAttempts: this._websocketConnectAttempts,
      websocketReconnects: this._websocketReconnects,
      websocketFailures: this._websocketFailures,
      envelopesReceived: this._envelopesReceived,
      envelopesDropped: this._envelopesDropped,
      protocolMismatches: this._protocolMismatches,
      snapshotHydrations: this._snapshotHydrations,
      snapshotHydrationFailures: this._snapshotHydrationFailures,
      renderErrors: this._renderErrors,
      lastEnvelopeAtMonotonicMs: this._lastEnvelopeAtMonotonicMs,
      layoutPanelMounts: this._layoutPanelMounts,
      recentPanelMounts: [...this._panelMountSamples],
      maxPanelMountMs: this._maxPanelMountMs,
      averagePanelMountMs,
      navigationsTotal: this._navigationsTotal,
      recentNavigations: [...this._navigationSamples],
      layoutObservabilityErrors: this._layoutObservabilityErrors,
    };
  }

  reset(): void {
    this._websocketConnectAttempts = 0;
    this._websocketReconnects = 0;
    this._websocketFailures = 0;
    this._envelopesReceived = 0;
    this._envelopesDropped = 0;
    this._protocolMismatches = 0;
    this._snapshotHydrations = 0;
    this._snapshotHydrationFailures = 0;
    this._renderErrors = 0;
    this._lastEnvelopeAtMonotonicMs = 0;
    this._layoutPanelMounts = 0;
    this._panelMountSamples = [];
    this._maxPanelMountMs = 0;
    this._totalPanelMountMs = 0;
    this._navigationsTotal = 0;
    this._navigationSamples = [];
    this._layoutObservabilityErrors = 0;
  }
}
