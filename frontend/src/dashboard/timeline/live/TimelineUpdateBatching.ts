/**
 * Microtask + rAF-aware update batcher.
 *
 * Many envelopes burst together — a websocket message can deliver a
 * single delta, a replay batch can deliver hundreds. The batcher
 * coalesces calls happening inside one event-loop turn (microtask
 * window) into a single flush. Larger windows (one rAF) are also
 * supported when the engine wants to align with the browser's paint
 * cadence.
 *
 * The batcher is *injection-friendly*: tests pass their own
 * ``queueMicrotask`` / ``raf`` / ``caf`` so flushes can be stepped
 * manually.
 */

export type ScheduleStrategy = "microtask" | "raf";

export interface BatchingOptions {
  strategy?: ScheduleStrategy;
  queueMicrotask?: (cb: () => void) => void;
  raf?: (cb: FrameRequestCallback) => number;
  caf?: (handle: number) => void;
}

export type FlushFn = () => void;

export class TimelineUpdateBatcher {
  private readonly strategy: ScheduleStrategy;
  private readonly _queueMicrotask: (cb: () => void) => void;
  private readonly _raf: (cb: FrameRequestCallback) => number;
  private readonly _caf: (handle: number) => void;
  private readonly flush: FlushFn;
  private pendingMicrotask = false;
  private pendingRafHandle: number | null = null;
  private _batchesScheduled = 0;
  private _batchesFlushed = 0;
  private _batchesCoalesced = 0;
  private disposed = false;

  constructor(flush: FlushFn, options: BatchingOptions = {}) {
    this.flush = flush;
    this.strategy = options.strategy ?? "microtask";
    this._queueMicrotask =
      options.queueMicrotask ??
      ((cb) => {
        if (typeof queueMicrotask === "function") queueMicrotask(cb);
        else Promise.resolve().then(cb);
      });
    this._raf =
      options.raf ??
      (typeof globalThis.requestAnimationFrame === "function"
        ? globalThis.requestAnimationFrame.bind(globalThis)
        : (cb: FrameRequestCallback) => setTimeout(() => cb(Date.now()), 16) as unknown as number);
    this._caf =
      options.caf ??
      (typeof globalThis.cancelAnimationFrame === "function"
        ? globalThis.cancelAnimationFrame.bind(globalThis)
        : (handle: number) => clearTimeout(handle as unknown as ReturnType<typeof setTimeout>));
  }

  /** Schedule a flush. Idempotent inside a single window. */
  schedule(): void {
    if (this.disposed) return;
    if (this.strategy === "microtask") {
      if (this.pendingMicrotask) {
        this._batchesCoalesced += 1;
        return;
      }
      this.pendingMicrotask = true;
      this._batchesScheduled += 1;
      this._queueMicrotask(() => this.runMicrotaskFlush());
    } else {
      if (this.pendingRafHandle !== null) {
        this._batchesCoalesced += 1;
        return;
      }
      this._batchesScheduled += 1;
      this.pendingRafHandle = this._raf(() => this.runRafFlush());
    }
  }

  /** Force a synchronous flush right now — used by replay coordinator
   *  on transition boundaries and by tests. */
  flushNow(): void {
    if (this.disposed) return;
    this.cancelPending();
    this._batchesFlushed += 1;
    this.flush();
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.cancelPending();
  }

  metrics(): {
    batchesScheduled: number;
    batchesFlushed: number;
    batchesCoalesced: number;
  } {
    return {
      batchesScheduled: this._batchesScheduled,
      batchesFlushed: this._batchesFlushed,
      batchesCoalesced: this._batchesCoalesced,
    };
  }

  private runMicrotaskFlush(): void {
    if (this.disposed) return;
    if (!this.pendingMicrotask) return;
    this.pendingMicrotask = false;
    this._batchesFlushed += 1;
    this.flush();
  }

  private runRafFlush(): void {
    if (this.disposed) return;
    this.pendingRafHandle = null;
    this._batchesFlushed += 1;
    this.flush();
  }

  private cancelPending(): void {
    this.pendingMicrotask = false;
    if (this.pendingRafHandle !== null) {
      this._caf(this.pendingRafHandle);
      this.pendingRafHandle = null;
    }
  }
}
