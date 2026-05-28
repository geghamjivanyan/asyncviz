/**
 * Sequence tracking + reconciliation.
 *
 * The backend stamps a monotonically-increasing ``sequence`` on every
 * ordered envelope (``runtime_event``, ``metrics_delta``,
 * ``warning_delta``, ``timeline_delta``). The client must:
 *
 *   * Apply each in-order envelope exactly once.
 *   * Drop duplicates (a reconnect's ``since_sequence`` window might
 *     overlap the last live frame).
 *   * Drop stale envelopes (server sometimes resurfaces older sequences
 *     while a snapshot is being applied — they were already reflected
 *     in the snapshot).
 *
 * The :class:`SequenceTracker` answers all three questions via
 * :meth:`accept`.
 */

export type SequenceDecision = "accept" | "stale" | "duplicate" | "out-of-order";

export interface SequenceTrackerSnapshot {
  lastSequence: number;
  accepted: number;
  duplicate: number;
  stale: number;
  outOfOrder: number;
}

export class SequenceTracker {
  private _lastSequence: number;
  private _accepted = 0;
  private _duplicate = 0;
  private _stale = 0;
  private _outOfOrder = 0;
  /** Optional cap on backward jumps that *aren't* a snapshot reset. */
  private readonly _allowBackwardSnapshot: boolean;

  constructor(initial: number = 0, { allowBackwardSnapshot = true } = {}) {
    this._lastSequence = initial;
    this._allowBackwardSnapshot = allowBackwardSnapshot;
  }

  get lastSequence(): number {
    return this._lastSequence;
  }

  /**
   * Decide what to do with ``sequence``.
   *
   * Returns:
   *
   *   * ``"accept"`` — strictly greater than the last seen sequence.
   *     The caller should apply the envelope and call :meth:`commit`.
   *   * ``"duplicate"`` — equal to the last seen sequence; the caller
   *     should drop the envelope.
   *   * ``"stale"`` — strictly less than the last seen sequence. The
   *     caller should drop the envelope.
   *   * ``"out-of-order"`` — non-monotonic gap detected. Today the
   *     client treats this the same as ``"accept"`` (the queue
   *     guarantees in-order delivery; gaps mean a reconnect happened
   *     and ``since_sequence`` is filling them in). Reserved for
   *     future strict-mode handling.
   *
   * ``sequence === null`` is the "unsequenced" channel — heartbeats,
   * system_status. Always accepted, never advances the cursor.
   */
  decide(sequence: number | null | undefined): SequenceDecision {
    if (sequence === null || sequence === undefined) {
      return "accept";
    }
    if (sequence > this._lastSequence) {
      const gap = sequence - this._lastSequence - 1;
      // A gap > 0 means the server jumped past one or more sequences
      // (replay catch-up landed in a different shape than expected).
      // We accept anyway — the queue's retention has them or it
      // doesn't; the snapshot path covers the cold-restart case.
      return gap === 0 ? "accept" : "out-of-order";
    }
    if (sequence === this._lastSequence) {
      return "duplicate";
    }
    return "stale";
  }

  /** Record an accept-decision and advance the cursor. */
  commit(sequence: number | null | undefined): void {
    if (sequence === null || sequence === undefined) return;
    this._accepted += 1;
    if (sequence > this._lastSequence) {
      this._lastSequence = sequence;
    }
  }

  /** Resnap the cursor (used after a ``runtime_snapshot`` envelope). */
  resnap(sequence: number): void {
    if (this._allowBackwardSnapshot || sequence > this._lastSequence) {
      this._lastSequence = sequence;
    }
  }

  /** Account for a dropped duplicate frame. */
  recordDuplicate(): void {
    this._duplicate += 1;
  }

  /** Account for a dropped stale frame. */
  recordStale(): void {
    this._stale += 1;
  }

  /** Account for an out-of-order frame (accepted; metric only). */
  recordOutOfOrder(): void {
    this._outOfOrder += 1;
  }

  snapshot(): SequenceTrackerSnapshot {
    return {
      lastSequence: this._lastSequence,
      accepted: this._accepted,
      duplicate: this._duplicate,
      stale: this._stale,
      outOfOrder: this._outOfOrder,
    };
  }

  reset(initial: number = 0): void {
    this._lastSequence = initial;
    this._accepted = 0;
    this._duplicate = 0;
    this._stale = 0;
    this._outOfOrder = 0;
  }
}
