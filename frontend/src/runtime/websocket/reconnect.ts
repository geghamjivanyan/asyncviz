/**
 * Reconnect backoff with deterministic jitter.
 *
 * The scheduler picks the next reconnect delay from an exponential
 * schedule capped at :data:`DEFAULT_MAX_DELAY_MS`. A small random
 * jitter prevents thundering-herd reconnects when many tabs / clients
 * detect the same backend restart. Tests inject a deterministic
 * random source via :data:`ReconnectOptions.random`.
 */

export interface ReconnectOptions {
  /** First delay; doubled each attempt. */
  baseDelayMs?: number;
  /** Maximum delay; the schedule clamps to this. */
  maxDelayMs?: number;
  /** Jitter fraction in [0, 1]. Final delay = base × (1 + random × jitter). */
  jitter?: number;
  /** Random source. Defaults to :func:`Math.random`. */
  random?: () => number;
  /** Optional cap on attempts. ``Infinity`` (default) reconnects forever. */
  maxAttempts?: number;
}

export const DEFAULT_BASE_DELAY_MS = 500;
export const DEFAULT_MAX_DELAY_MS = 15_000;
export const DEFAULT_JITTER = 0.2;

export interface ReconnectSchedule {
  attempt: number;
  delayMs: number;
}

export class ReconnectScheduler {
  private _attempt = 0;
  private readonly _baseDelayMs: number;
  private readonly _maxDelayMs: number;
  private readonly _jitter: number;
  private readonly _random: () => number;
  private readonly _maxAttempts: number;

  constructor(options: ReconnectOptions = {}) {
    this._baseDelayMs = options.baseDelayMs ?? DEFAULT_BASE_DELAY_MS;
    this._maxDelayMs = options.maxDelayMs ?? DEFAULT_MAX_DELAY_MS;
    this._jitter = options.jitter ?? DEFAULT_JITTER;
    this._random = options.random ?? Math.random;
    this._maxAttempts = options.maxAttempts ?? Infinity;
  }

  get attempt(): number {
    return this._attempt;
  }

  get maxAttempts(): number {
    return this._maxAttempts;
  }

  reset(): void {
    this._attempt = 0;
  }

  /** Whether another reconnect attempt is allowed. */
  hasAttemptsRemaining(): boolean {
    return this._attempt < this._maxAttempts;
  }

  /**
   * Compute the next delay + advance the attempt counter.
   *
   * Returns ``null`` when the attempts cap has been reached — the
   * caller should transition to ``FAILED``.
   */
  next(): ReconnectSchedule | null {
    if (!this.hasAttemptsRemaining()) {
      return null;
    }
    this._attempt += 1;
    const exponent = Math.min(this._attempt - 1, 30);
    const baseExp = this._baseDelayMs * 2 ** exponent;
    const capped = Math.min(baseExp, this._maxDelayMs);
    const jitterMultiplier = 1 + this._random() * this._jitter;
    const delayMs = Math.min(this._maxDelayMs, Math.round(capped * jitterMultiplier));
    return { attempt: this._attempt, delayMs };
  }
}
