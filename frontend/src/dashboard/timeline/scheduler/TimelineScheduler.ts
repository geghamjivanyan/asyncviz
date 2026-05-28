/**
 * Frame scheduler for the timeline renderer.
 *
 * The scheduler exists so the renderer doesn't spin uncontrolled
 * ``requestAnimationFrame`` loops. It owns three things:
 *
 *   1. A dirty flag — flipped by callers when something must be
 *      redrawn (data change, viewport resize, camera pan).
 *   2. A single in-flight rAF token.
 *   3. The frame callback that clears the flag + invokes the render
 *      function.
 *
 * The scheduler is *injection-friendly*: tests pass their own
 * ``raf`` / ``caf`` pair so frames can be stepped manually.
 */

export type RafFn = (callback: FrameRequestCallback) => number;
export type CafFn = (handle: number) => void;

export interface SchedulerOptions {
  raf?: RafFn;
  caf?: CafFn;
}

export type DirtyReason = "viewport" | "camera" | "data" | "selection" | "overlay" | "manual";

export class TimelineScheduler {
  private readonly raf: RafFn;
  private readonly caf: CafFn;
  private readonly render: () => void;
  private dirty = false;
  private pending: number | null = null;
  private reasons = new Set<DirtyReason>();
  private framesScheduled = 0;
  private framesRendered = 0;
  private framesDropped = 0;
  private disposed = false;

  constructor(render: () => void, options: SchedulerOptions = {}) {
    this.render = render;
    this.raf =
      options.raf ??
      (typeof globalThis.requestAnimationFrame === "function"
        ? globalThis.requestAnimationFrame.bind(globalThis)
        : (cb: FrameRequestCallback) => setTimeout(() => cb(Date.now()), 16) as unknown as number);
    this.caf =
      options.caf ??
      (typeof globalThis.cancelAnimationFrame === "function"
        ? globalThis.cancelAnimationFrame.bind(globalThis)
        : (handle: number) => clearTimeout(handle as unknown as ReturnType<typeof setTimeout>));
  }

  /** Flip the dirty flag + schedule a frame if one isn't pending. */
  invalidate(reason: DirtyReason = "manual"): void {
    if (this.disposed) return;
    this.dirty = true;
    this.reasons.add(reason);
    if (this.pending === null) {
      this.framesScheduled += 1;
      this.pending = this.raf(this.tick);
    }
  }

  /** Returns the set of dirty reasons that triggered the *next* frame.
   *  Cleared at the start of the frame. */
  pendingReasons(): readonly DirtyReason[] {
    return Array.from(this.reasons);
  }

  /** Synchronously render right now, bypassing rAF. Used in tests
   *  + for the initial mount. */
  forceRender(): void {
    if (this.disposed) return;
    this.dirty = false;
    this.reasons.clear();
    this.render();
    this.framesRendered += 1;
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    if (this.pending !== null) {
      this.caf(this.pending);
      this.pending = null;
    }
    this.dirty = false;
    this.reasons.clear();
  }

  metrics(): SchedulerMetricsSnapshot {
    return {
      framesScheduled: this.framesScheduled,
      framesRendered: this.framesRendered,
      framesDropped: this.framesDropped,
    };
  }

  private tick = (): void => {
    this.pending = null;
    if (this.disposed) return;
    if (!this.dirty) {
      this.framesDropped += 1;
      return;
    }
    this.dirty = false;
    this.reasons.clear();
    this.render();
    this.framesRendered += 1;
  };
}

export interface SchedulerMetricsSnapshot {
  framesScheduled: number;
  framesRendered: number;
  framesDropped: number;
}
