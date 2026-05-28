/**
 * Rolling rate tracker.
 *
 * Computes events-per-second over a fixed window. The implementation
 * uses a bounded ring buffer of (timestamp, count) samples — old
 * samples are evicted as new ones arrive. This is intentionally
 * simple: the metrics header is rendered at human-scale cadence (1Hz)
 * so we don't need a histogram-grade structure.
 *
 * The tracker is pure-stateful: ``record`` returns the next instance,
 * tests can step through deterministically.
 */

const DEFAULT_WINDOW_MS = 5_000;
const SAMPLE_CAPACITY = 64;

export interface RateSample {
  recordedAtMs: number;
  totalAtSample: number;
}

export interface RateTrackerState {
  samples: readonly RateSample[];
  windowMs: number;
  capacity: number;
}

export function createRateTracker(opts?: {
  windowMs?: number;
  capacity?: number;
}): RateTrackerState {
  return {
    samples: [],
    windowMs: opts?.windowMs ?? DEFAULT_WINDOW_MS,
    capacity: opts?.capacity ?? SAMPLE_CAPACITY,
  };
}

/** Pure: record a new total observation. Returns a fresh state. */
export function recordRateSample(
  state: RateTrackerState,
  total: number,
  nowMs: number,
): RateTrackerState {
  const cutoff = nowMs - state.windowMs;
  const filtered = state.samples.filter((s) => s.recordedAtMs >= cutoff);
  const next: RateSample[] = [...filtered, { recordedAtMs: nowMs, totalAtSample: total }];
  if (next.length > state.capacity) {
    next.splice(0, next.length - state.capacity);
  }
  return { ...state, samples: next };
}

/** Pure: rate per second across the recorded window. */
export function rateFromTracker(state: RateTrackerState, nowMs: number): number {
  if (state.samples.length < 2) return 0;
  const cutoff = nowMs - state.windowMs;
  const inWindow = state.samples.filter((s) => s.recordedAtMs >= cutoff);
  if (inWindow.length < 2) return 0;
  const first = inWindow[0]!;
  const last = inWindow[inWindow.length - 1]!;
  const dtMs = last.recordedAtMs - first.recordedAtMs;
  if (dtMs <= 0) return 0;
  const delta = last.totalAtSample - first.totalAtSample;
  if (delta <= 0) return 0;
  return (delta * 1000) / dtMs;
}
