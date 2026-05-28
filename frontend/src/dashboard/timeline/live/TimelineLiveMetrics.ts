/**
 * Observability counters for the live timeline update engine.
 *
 * Mirrors the established pattern (one class per subsystem, frozen
 * snapshot view, module-level lazy singleton + reset helper).
 */

import type { InvalidationReason, TimelineLiveMode } from "@/dashboard/timeline/live/models/TimelineLiveModels";

export interface TimelineLiveMetricsSnapshot {
  envelopesObserved: number;
  envelopesSuppressed: number;
  invalidationsByReason: Record<InvalidationReason, number>;
  batchesEmitted: number;
  batchRegionsCoalesced: number;
  flushesScheduled: number;
  flushesExecuted: number;
  flushesSkippedIdle: number;
  replayBatchesApplied: number;
  replayEnvelopesApplied: number;
  liveEnvelopesApplied: number;
  activeTicks: number;
  activeTicksSuppressed: number;
  lastBatchLatencyMs: number;
  maxBatchLatencyMs: number;
  totalBatchLatencyMs: number;
  lastFlushAtMs: number;
  currentMode: TimelineLiveMode;
}

function emptyReasons(): Record<InvalidationReason, number> {
  return {
    row: 0,
    segment: 0,
    viewport: 0,
    selection: 0,
    warning: 0,
    replay: 0,
    "active-tick": 0,
    manual: 0,
    "delta-batch": 0,
    hydration: 0,
  };
}

export class TimelineLiveMetrics {
  private _envelopesObserved = 0;
  private _envelopesSuppressed = 0;
  private _invalidationsByReason: Record<InvalidationReason, number> = emptyReasons();
  private _batchesEmitted = 0;
  private _batchRegionsCoalesced = 0;
  private _flushesScheduled = 0;
  private _flushesExecuted = 0;
  private _flushesSkippedIdle = 0;
  private _replayBatchesApplied = 0;
  private _replayEnvelopesApplied = 0;
  private _liveEnvelopesApplied = 0;
  private _activeTicks = 0;
  private _activeTicksSuppressed = 0;
  private _lastBatchLatencyMs = 0;
  private _maxBatchLatencyMs = 0;
  private _totalBatchLatencyMs = 0;
  private _lastFlushAtMs = 0;
  private _currentMode: TimelineLiveMode = "idle";

  recordEnvelope(suppressed: boolean): void {
    this._envelopesObserved += 1;
    if (suppressed) this._envelopesSuppressed += 1;
  }

  recordInvalidation(reason: InvalidationReason): void {
    this._invalidationsByReason[reason] = (this._invalidationsByReason[reason] ?? 0) + 1;
  }

  recordBatch(regionCount: number, latencyMs: number, atMs: number): void {
    this._batchesEmitted += 1;
    this._batchRegionsCoalesced += regionCount;
    if (Number.isFinite(latencyMs) && latencyMs >= 0) {
      this._totalBatchLatencyMs += latencyMs;
      this._lastBatchLatencyMs = latencyMs;
      if (latencyMs > this._maxBatchLatencyMs) this._maxBatchLatencyMs = latencyMs;
    }
    this._lastFlushAtMs = atMs;
  }

  recordFlushScheduled(): void {
    this._flushesScheduled += 1;
  }

  recordFlushExecuted(): void {
    this._flushesExecuted += 1;
  }

  recordFlushSkippedIdle(): void {
    this._flushesSkippedIdle += 1;
  }

  recordReplayBatch(envelopesApplied: number): void {
    this._replayBatchesApplied += 1;
    this._replayEnvelopesApplied += envelopesApplied;
  }

  recordLiveEnvelope(): void {
    this._liveEnvelopesApplied += 1;
  }

  recordActiveTick(suppressed: boolean): void {
    if (suppressed) this._activeTicksSuppressed += 1;
    else this._activeTicks += 1;
  }

  setMode(mode: TimelineLiveMode): void {
    this._currentMode = mode;
  }

  snapshot(): TimelineLiveMetricsSnapshot {
    return {
      envelopesObserved: this._envelopesObserved,
      envelopesSuppressed: this._envelopesSuppressed,
      invalidationsByReason: { ...this._invalidationsByReason },
      batchesEmitted: this._batchesEmitted,
      batchRegionsCoalesced: this._batchRegionsCoalesced,
      flushesScheduled: this._flushesScheduled,
      flushesExecuted: this._flushesExecuted,
      flushesSkippedIdle: this._flushesSkippedIdle,
      replayBatchesApplied: this._replayBatchesApplied,
      replayEnvelopesApplied: this._replayEnvelopesApplied,
      liveEnvelopesApplied: this._liveEnvelopesApplied,
      activeTicks: this._activeTicks,
      activeTicksSuppressed: this._activeTicksSuppressed,
      lastBatchLatencyMs: this._lastBatchLatencyMs,
      maxBatchLatencyMs: this._maxBatchLatencyMs,
      totalBatchLatencyMs: this._totalBatchLatencyMs,
      lastFlushAtMs: this._lastFlushAtMs,
      currentMode: this._currentMode,
    };
  }

  reset(): void {
    this._envelopesObserved = 0;
    this._envelopesSuppressed = 0;
    this._invalidationsByReason = emptyReasons();
    this._batchesEmitted = 0;
    this._batchRegionsCoalesced = 0;
    this._flushesScheduled = 0;
    this._flushesExecuted = 0;
    this._flushesSkippedIdle = 0;
    this._replayBatchesApplied = 0;
    this._replayEnvelopesApplied = 0;
    this._liveEnvelopesApplied = 0;
    this._activeTicks = 0;
    this._activeTicksSuppressed = 0;
    this._lastBatchLatencyMs = 0;
    this._maxBatchLatencyMs = 0;
    this._totalBatchLatencyMs = 0;
    this._lastFlushAtMs = 0;
    this._currentMode = "idle";
  }
}

let _instance: TimelineLiveMetrics | null = null;

export function getTimelineLiveMetrics(): TimelineLiveMetrics {
  if (_instance === null) _instance = new TimelineLiveMetrics();
  return _instance;
}

export function resetTimelineLiveMetrics(): void {
  if (_instance !== null) _instance.reset();
}
