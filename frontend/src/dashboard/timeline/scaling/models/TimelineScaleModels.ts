/**
 * Types for the canonical time-scaling engine.
 *
 * The scale engine deals in two coordinate spaces:
 *
 *   * world time — monotonic seconds, an arbitrary-precision double,
 *   * screen x — CSS pixels relative to the canvas origin.
 *
 * Every operation routes through an immutable :type:`TimelineTimeScale`
 * so transforms stay deterministic + replay-safe.
 */

/** Frozen scale primitive — time ↔ x transform parameters. */
export interface TimelineScaleSnapshot {
  /** Left edge of the visible window in world seconds. */
  timeStart: number;
  /** Right edge of the visible window in world seconds. */
  timeEnd: number;
  /** Horizontal viewport width in CSS pixels. */
  widthPx: number;
  /** Pre-computed visible duration (seconds, always > 0). */
  durationSeconds: number;
  /** Pre-computed pixels per world second. */
  pixelsPerSecond: number;
  /** Pre-computed inverse: seconds per CSS pixel. */
  secondsPerPixel: number;
  /** Stable identity for cache lookups — compare by ``===``. */
  key: string;
}

/** Scale constraints — defensive bounds the engine enforces. */
export interface ScaleConstraints {
  /** Minimum visible duration (seconds). Stops zoom-in at the
   *  resolution of the timeline. */
  minDurationSeconds: number;
  /** Maximum visible duration (seconds). Stops zoom-out at the
   *  total replay length (or a defensive ceiling). */
  maxDurationSeconds: number;
  /** Minimum world time the camera is allowed to display. */
  minTimeSeconds: number | null;
  /** Maximum world time the camera is allowed to display. */
  maxTimeSeconds: number | null;
}

export const DEFAULT_SCALE_CONSTRAINTS: ScaleConstraints = Object.freeze({
  minDurationSeconds: 1e-6,
  maxDurationSeconds: 1e9,
  minTimeSeconds: null,
  maxTimeSeconds: null,
});

/** Single tick on the time axis. */
export interface TimelineScaleTick {
  /** World time the tick corresponds to. */
  timeSeconds: number;
  /** Pre-computed CSS x coordinate. */
  xCss: number;
  /** ``true`` for major ticks (drawn brighter, labeled). */
  major: boolean;
  /** Human-readable label, or ``null`` for minor ticks. */
  label: string | null;
}

/** Tick list snapshot — the engine caches one per scale key. */
export interface TimelineTickList {
  ticks: readonly TimelineScaleTick[];
  /** The interval (seconds) chosen for *major* ticks. */
  majorIntervalSeconds: number;
  /** The interval (seconds) chosen for *minor* ticks. */
  minorIntervalSeconds: number;
  /** Stable cache key (matches the scale key it was built for). */
  key: string;
}

/** Interpolation context used by future animated zoom controllers. */
export interface ScaleInterpolationFrame {
  fromTimeStart: number;
  fromTimeEnd: number;
  toTimeStart: number;
  toTimeEnd: number;
  /** Phase in [0, 1]. */
  t: number;
}
