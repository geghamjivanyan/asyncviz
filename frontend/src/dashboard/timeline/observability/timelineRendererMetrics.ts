/**
 * Observability counters for the canvas timeline renderer.
 *
 * Mirrors the established pattern: one class per subsystem, frozen
 * snapshot view, no module-level singleton in tests. The shared
 * instance returned by :func:`getTimelineRendererMetrics` is used by
 * the live renderer.
 */

import type { DirtyReason } from "@/dashboard/timeline/scheduler/TimelineScheduler";

export interface TimelineRendererMetricsSnapshot {
  /** Total frames rendered through :class:`TimelineRenderer.renderFrame`. */
  framesRendered: number;
  /** Total frame durations (sum, ms). */
  frameDurationTotalMs: number;
  /** Last observed frame duration (ms). */
  lastFrameDurationMs: number;
  /** Max observed frame duration (ms). */
  maxFrameDurationMs: number;
  /** Total visible-row count observed (sum). */
  visibleRowsTotal: number;
  /** Total visible-segment count observed (sum). */
  visibleSegmentsTotal: number;
  /** Invalidation counts broken out by reason. */
  invalidationsByReason: Record<DirtyReason, number>;
  /** Resize events recorded. */
  resizeEvents: number;
  /** Dropped-frame indicator (frames whose duration exceeded the budget). */
  droppedFrameWarnings: number;
}

const FRAME_BUDGET_MS = 16;

export class TimelineRendererMetrics {
  private _framesRendered = 0;
  private _frameDurationTotalMs = 0;
  private _lastFrameDurationMs = 0;
  private _maxFrameDurationMs = 0;
  private _visibleRowsTotal = 0;
  private _visibleSegmentsTotal = 0;
  private _resizeEvents = 0;
  private _droppedFrameWarnings = 0;
  private _invalidationsByReason: Record<DirtyReason, number> = {
    viewport: 0,
    camera: 0,
    data: 0,
    selection: 0,
    overlay: 0,
    manual: 0,
  };

  recordFrame(args: {
    durationMs: number;
    visibleRowCount: number;
    visibleSegmentCount: number;
  }): void {
    this._framesRendered += 1;
    this._visibleRowsTotal += args.visibleRowCount;
    this._visibleSegmentsTotal += args.visibleSegmentCount;
    if (Number.isFinite(args.durationMs) && args.durationMs >= 0) {
      this._frameDurationTotalMs += args.durationMs;
      this._lastFrameDurationMs = args.durationMs;
      if (args.durationMs > this._maxFrameDurationMs) {
        this._maxFrameDurationMs = args.durationMs;
      }
      if (args.durationMs > FRAME_BUDGET_MS) {
        this._droppedFrameWarnings += 1;
      }
    }
  }

  recordInvalidation(reason: DirtyReason): void {
    this._invalidationsByReason[reason] = (this._invalidationsByReason[reason] ?? 0) + 1;
  }

  recordResize(): void {
    this._resizeEvents += 1;
  }

  snapshot(): TimelineRendererMetricsSnapshot {
    return {
      framesRendered: this._framesRendered,
      frameDurationTotalMs: this._frameDurationTotalMs,
      lastFrameDurationMs: this._lastFrameDurationMs,
      maxFrameDurationMs: this._maxFrameDurationMs,
      visibleRowsTotal: this._visibleRowsTotal,
      visibleSegmentsTotal: this._visibleSegmentsTotal,
      invalidationsByReason: { ...this._invalidationsByReason },
      resizeEvents: this._resizeEvents,
      droppedFrameWarnings: this._droppedFrameWarnings,
    };
  }

  reset(): void {
    this._framesRendered = 0;
    this._frameDurationTotalMs = 0;
    this._lastFrameDurationMs = 0;
    this._maxFrameDurationMs = 0;
    this._visibleRowsTotal = 0;
    this._visibleSegmentsTotal = 0;
    this._resizeEvents = 0;
    this._droppedFrameWarnings = 0;
    this._invalidationsByReason = {
      viewport: 0,
      camera: 0,
      data: 0,
      selection: 0,
      overlay: 0,
      manual: 0,
    };
  }
}

let _instance: TimelineRendererMetrics | null = null;

export function getTimelineRendererMetrics(): TimelineRendererMetrics {
  if (_instance === null) _instance = new TimelineRendererMetrics();
  return _instance;
}

export function resetTimelineRendererMetrics(): void {
  if (_instance !== null) _instance.reset();
}
