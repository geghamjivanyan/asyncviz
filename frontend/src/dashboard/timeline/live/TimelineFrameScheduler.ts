/**
 * Live-engine-side frame scheduler facade.
 *
 * The canvas renderer already has a low-level :class:`TimelineScheduler`
 * that owns ``requestAnimationFrame``. The live engine doesn't try to
 * own a parallel rAF loop — it pushes invalidations into the
 * renderer's scheduler. This module is a thin facade that exists so
 * the live-side bookkeeping (counts, idle-frame suppression policy,
 * dropped-frame detection) stays separate from the renderer.
 *
 * Today the facade just delegates. Tomorrow it'll grow:
 *
 *   * frame budget enforcement (skip if frame > 16ms),
 *   * idle suppression (skip when nothing is dirty),
 *   * backpressure throttling under sustained delta storms.
 */

import type { DirtyReason } from "@/dashboard/timeline/scheduler/TimelineScheduler";

export interface FrameRequestSink {
  invalidate(reason: DirtyReason): void;
}

export interface FrameSchedulerOptions {
  /** Hard ceiling on how many flushes we'll request per second. ``0``
   *  disables throttling (the renderer's rAF cap remains). */
  maxFlushesPerSecond?: number;
  /** Injectable clock for tests. */
  now?: () => number;
}

export class TimelineFrameScheduler {
  private readonly sink: FrameRequestSink;
  private readonly maxFlushesPerSecond: number;
  private readonly now: () => number;
  private _frameRequests = 0;
  private _frameRequestsSuppressed = 0;
  private _lastRequestMs = -Infinity;

  constructor(sink: FrameRequestSink, options: FrameSchedulerOptions = {}) {
    this.sink = sink;
    this.maxFlushesPerSecond = Math.max(0, options.maxFlushesPerSecond ?? 0);
    this.now =
      options.now ?? (() => (typeof performance !== "undefined" ? performance.now() : Date.now()));
  }

  /** Request a frame from the renderer with the given dirty reason.
   *  Returns ``true`` when the request was forwarded, ``false`` when
   *  throttled. */
  requestFrame(reason: DirtyReason): boolean {
    if (this.maxFlushesPerSecond > 0) {
      const now = this.now();
      const minIntervalMs = 1000 / this.maxFlushesPerSecond;
      if (now - this._lastRequestMs < minIntervalMs) {
        this._frameRequestsSuppressed += 1;
        return false;
      }
      this._lastRequestMs = now;
    }
    this._frameRequests += 1;
    this.sink.invalidate(reason);
    return true;
  }

  metrics(): {
    frameRequests: number;
    frameRequestsSuppressed: number;
  } {
    return {
      frameRequests: this._frameRequests,
      frameRequestsSuppressed: this._frameRequestsSuppressed,
    };
  }
}
