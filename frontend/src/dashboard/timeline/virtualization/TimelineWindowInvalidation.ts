/**
 * Invalidation triggers consumed by the virtualization engine.
 *
 * The engine watches a tiny set of signals to know when its caches
 * must be flushed:
 *
 *   * dataset sequence advanced — full cache flush,
 *   * camera changed — viewport cache miss (the window key already
 *     captures camera state),
 *   * viewport changed — same as above,
 *   * overscan changed — flush the window snapshot.
 *
 * Today the helpers here are simple flag-based; tomorrow they'll
 * grow into pluggable invalidation streams (e.g. "row at index 42
 * changed only") once partial-row updates land.
 */

import type { TimelineLiveEngine } from "@/dashboard/timeline/live/TimelineLiveEngine";

export interface InvalidationSubscription {
  unsubscribe(): void;
}

export interface InvalidationSink {
  invalidate(): void;
}

/**
 * Wrap the live engine into a callable invalidation sink so the
 * virtualization engine can ping it from anywhere.
 */
export function invalidationSinkFromLiveEngine(engine: TimelineLiveEngine): InvalidationSink {
  return {
    invalidate: () => engine.invalidateAll(),
  };
}
