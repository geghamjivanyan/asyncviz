/**
 * Observability counters for the freeze-region layer.
 *
 * Mirrors the established per-subsystem pattern. The singleton
 * instance is read by the diagnostics panel; tests poke
 * :func:`resetFreezeRegionMetrics` between assertions.
 */

export interface FreezeRegionMetricsSnapshot {
  framesRendered: number;
  freezesProjected: number;
  freezesRenderedTotal: number;
  freezesCulled: number;
  visibleCapTruncations: number;
  selectionChanges: number;
  hoverChanges: number;
  revealCalls: number;
  /** Last few frame durations (ms). */
  recentFrameDurationsMs: readonly number[];
  /** Max frame duration observed (ms). */
  maxFrameDurationMs: number;
  /** Avg frame duration (ms). */
  averageFrameDurationMs: number;
  /** Last visible region count. */
  lastVisibleCount: number;
  /** Last hidden (capped) count. */
  lastHiddenCount: number;
}

const SAMPLE_RING_CAPACITY = 16;

class FreezeRegionMetrics {
  private _frames = 0;
  private _projected = 0;
  private _renderedTotal = 0;
  private _culled = 0;
  private _truncations = 0;
  private _selectionChanges = 0;
  private _hoverChanges = 0;
  private _revealCalls = 0;
  private _ring: number[] = [];
  private _totalMs = 0;
  private _maxMs = 0;
  private _lastVisible = 0;
  private _lastHidden = 0;

  recordFrame(args: {
    durationMs: number;
    visibleCount: number;
    hiddenCount: number;
    culledCount: number;
  }): void {
    this._frames += 1;
    this._lastVisible = args.visibleCount;
    this._lastHidden = args.hiddenCount;
    this._renderedTotal += args.visibleCount;
    this._culled += args.culledCount;
    if (args.hiddenCount > 0) this._truncations += 1;
    if (Number.isFinite(args.durationMs) && args.durationMs >= 0) {
      this._totalMs += args.durationMs;
      if (args.durationMs > this._maxMs) this._maxMs = args.durationMs;
      this._ring.push(args.durationMs);
      while (this._ring.length > SAMPLE_RING_CAPACITY) this._ring.shift();
    }
  }

  recordProjection(count: number): void {
    this._projected += count;
  }

  recordSelectionChange(): void {
    this._selectionChanges += 1;
  }

  recordHoverChange(): void {
    this._hoverChanges += 1;
  }

  recordReveal(): void {
    this._revealCalls += 1;
  }

  snapshot(): FreezeRegionMetricsSnapshot {
    const avg = this._ring.length === 0 ? 0 : this._totalMs / this._ring.length;
    return {
      framesRendered: this._frames,
      freezesProjected: this._projected,
      freezesRenderedTotal: this._renderedTotal,
      freezesCulled: this._culled,
      visibleCapTruncations: this._truncations,
      selectionChanges: this._selectionChanges,
      hoverChanges: this._hoverChanges,
      revealCalls: this._revealCalls,
      recentFrameDurationsMs: [...this._ring],
      maxFrameDurationMs: this._maxMs,
      averageFrameDurationMs: avg,
      lastVisibleCount: this._lastVisible,
      lastHiddenCount: this._lastHidden,
    };
  }

  reset(): void {
    this._frames = 0;
    this._projected = 0;
    this._renderedTotal = 0;
    this._culled = 0;
    this._truncations = 0;
    this._selectionChanges = 0;
    this._hoverChanges = 0;
    this._revealCalls = 0;
    this._ring = [];
    this._totalMs = 0;
    this._maxMs = 0;
    this._lastVisible = 0;
    this._lastHidden = 0;
  }
}

const _instance = new FreezeRegionMetrics();

export function getFreezeRegionMetrics(): FreezeRegionMetrics {
  return _instance;
}

export function resetFreezeRegionMetrics(): void {
  _instance.reset();
}

export type { FreezeRegionMetrics };
