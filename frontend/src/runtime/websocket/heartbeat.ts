/**
 * Heartbeat liveness monitor.
 *
 * The backend emits ``heartbeat`` envelopes at a fixed cadence. The
 * monitor records every incoming frame (any frame, not just
 * heartbeats — any traffic resets the staleness timer) and fires
 * ``onStale`` if no traffic is seen for ``staleThresholdMs``. The
 * websocket client uses ``onStale`` to force a reconnect.
 *
 * Uses ``setTimeout`` so it works under JSDOM + fake timers in tests.
 */

export interface HeartbeatOptions {
  staleThresholdMs?: number;
  /** Replaced by tests; defaults to ``setTimeout`` / ``clearTimeout``. */
  setTimer?: (callback: () => void, ms: number) => unknown;
  clearTimer?: (id: unknown) => void;
  now?: () => number;
}

export const DEFAULT_STALE_THRESHOLD_MS = 30_000;

export class HeartbeatMonitor {
  private _lastFrameAt = 0;
  private _heartbeatsSeen = 0;
  private _staleTriggers = 0;
  private _timerId: unknown = null;
  private readonly _setTimer: (callback: () => void, ms: number) => unknown;
  private readonly _clearTimer: (id: unknown) => void;
  private readonly _now: () => number;
  private readonly _staleThresholdMs: number;
  private _onStale: (() => void) | null = null;

  constructor(options: HeartbeatOptions = {}) {
    this._staleThresholdMs = options.staleThresholdMs ?? DEFAULT_STALE_THRESHOLD_MS;
    this._setTimer = options.setTimer ?? ((cb, ms) => setTimeout(cb, ms));
    this._clearTimer =
      options.clearTimer ?? ((id) => clearTimeout(id as ReturnType<typeof setTimeout>));
    this._now = options.now ?? (() => performance.now());
  }

  get lastFrameAt(): number {
    return this._lastFrameAt;
  }

  get heartbeatsSeen(): number {
    return this._heartbeatsSeen;
  }

  get staleTriggers(): number {
    return this._staleTriggers;
  }

  start(onStale: () => void): void {
    this._onStale = onStale;
    this._lastFrameAt = this._now();
    this._scheduleNext();
  }

  stop(): void {
    if (this._timerId !== null) {
      this._clearTimer(this._timerId);
      this._timerId = null;
    }
    this._onStale = null;
  }

  /** Call on any incoming frame; resets the staleness timer. */
  recordFrame(isHeartbeat: boolean = false): void {
    this._lastFrameAt = this._now();
    if (isHeartbeat) {
      this._heartbeatsSeen += 1;
    }
    if (this._onStale !== null) {
      this._scheduleNext();
    }
  }

  private _scheduleNext(): void {
    if (this._timerId !== null) {
      this._clearTimer(this._timerId);
    }
    this._timerId = this._setTimer(() => {
      this._timerId = null;
      this._staleTriggers += 1;
      this._onStale?.();
    }, this._staleThresholdMs);
  }
}
