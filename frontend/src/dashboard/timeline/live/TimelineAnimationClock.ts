/**
 * Animation clock for live timeline updates.
 *
 * Active running / waiting segments visually extend to the camera's
 * right edge — but the renderer won't repaint unless something tells
 * it to. The animation clock is that "something": it requests one
 * frame per rAF tick *only* while there is at least one active
 * segment. When the active count drops to zero, the clock parks
 * itself and the renderer stops spinning.
 *
 * The clock owns a single rAF reservation; rapid changes to the
 * active count don't pile up. ``raf`` / ``caf`` are injectable for
 * tests.
 */

export type AnimationTickListener = () => void;

export interface AnimationClockOptions {
  raf?: (cb: FrameRequestCallback) => number;
  caf?: (handle: number) => void;
  /** Maximum sustained ticks per second. ``0`` disables the cap. */
  maxTicksPerSecond?: number;
  now?: () => number;
}

export class TimelineAnimationClock {
  private readonly listener: AnimationTickListener;
  private readonly raf: (cb: FrameRequestCallback) => number;
  private readonly caf: (handle: number) => void;
  private readonly maxTicksPerSecond: number;
  private readonly now: () => number;
  private pendingHandle: number | null = null;
  private activeCount = 0;
  private running = false;
  private _ticks = 0;
  private _ticksSuppressed = 0;
  private _starts = 0;
  private _stops = 0;
  private _lastTickMs = -Infinity;
  private disposed = false;

  constructor(listener: AnimationTickListener, options: AnimationClockOptions = {}) {
    this.listener = listener;
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
    this.maxTicksPerSecond = Math.max(0, options.maxTicksPerSecond ?? 0);
    this.now =
      options.now ?? (() => (typeof performance !== "undefined" ? performance.now() : Date.now()));
  }

  /** Sync the engine's idea of how many active segments are in
   *  flight. Starts the clock at first transition to > 0, stops it
   *  when it returns to 0. */
  setActiveSegmentCount(count: number): void {
    const next = Math.max(0, Math.floor(count));
    if (next === this.activeCount) return;
    const wasRunning = this.running;
    this.activeCount = next;
    if (next > 0 && !wasRunning) this.start();
    else if (next === 0 && wasRunning) this.stop();
  }

  /** ``true`` while the clock has a frame reservation. */
  isRunning(): boolean {
    return this.running;
  }

  /** Force-stop the clock without touching the active count. Used by
   *  pause/replay transitions. */
  pause(): void {
    if (!this.running) return;
    this.stop();
  }

  /** Resume the clock if there are still active segments. */
  resume(): void {
    if (this.running || this.disposed || this.activeCount === 0) return;
    this.start();
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.stop();
  }

  metrics(): {
    activeCount: number;
    running: boolean;
    ticks: number;
    ticksSuppressed: number;
    starts: number;
    stops: number;
  } {
    return {
      activeCount: this.activeCount,
      running: this.running,
      ticks: this._ticks,
      ticksSuppressed: this._ticksSuppressed,
      starts: this._starts,
      stops: this._stops,
    };
  }

  // ── internals ────────────────────────────────────────────────────

  private start(): void {
    if (this.disposed || this.running) return;
    this.running = true;
    this._starts += 1;
    this.scheduleNext();
  }

  private stop(): void {
    this.running = false;
    if (this.pendingHandle !== null) {
      this.caf(this.pendingHandle);
      this.pendingHandle = null;
    }
    this._stops += 1;
  }

  private scheduleNext(): void {
    if (!this.running || this.pendingHandle !== null) return;
    this.pendingHandle = this.raf(this.tick);
  }

  private tick = (): void => {
    this.pendingHandle = null;
    if (!this.running || this.disposed) return;
    if (this.maxTicksPerSecond > 0) {
      const now = this.now();
      const minIntervalMs = 1000 / this.maxTicksPerSecond;
      if (now - this._lastTickMs < minIntervalMs) {
        this._ticksSuppressed += 1;
        this.scheduleNext();
        return;
      }
      this._lastTickMs = now;
    }
    this._ticks += 1;
    try {
      this.listener();
    } finally {
      this.scheduleNext();
    }
  };
}
