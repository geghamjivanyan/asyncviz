/**
 * Tiny precision-friendly numeric helpers used by the scaling engine.
 *
 * The helpers stay deliberately simple — the goal is to make
 * floating-point edge cases explicit at the call sites that care.
 */

/** Smallest meaningful gap between two seconds values the engine
 *  treats as distinct. Smaller deltas collapse to zero. */
export const SCALE_EPSILON_SECONDS = 1e-9;

/** Pure: clamp ``value`` into the closed interval ``[min, max]``. */
export function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  if (value < min) return min;
  if (value > max) return max;
  return value;
}

/** Pure: ``true`` when ``a`` and ``b`` agree within ``epsilon``. */
export function approximatelyEqual(
  a: number,
  b: number,
  epsilon: number = SCALE_EPSILON_SECONDS,
): boolean {
  if (a === b) return true;
  return Math.abs(a - b) <= epsilon;
}

/** Pure: snap ``value`` to the nearest sub-pixel grid step. Used to
 *  keep crisp strokes when devices share a sub-pixel boundary. */
export function snapToPixel(value: number, devicePixelRatio: number): number {
  if (!Number.isFinite(value) || devicePixelRatio <= 0) return value;
  const step = 1 / devicePixelRatio;
  return Math.round(value / step) * step;
}

/** Pure: a numerical safety check — ``true`` when ``duration`` is too
 *  small to render distinct segments at any reasonable scale. */
export function durationTooSmall(durationSeconds: number, minSeconds: number): boolean {
  if (!Number.isFinite(durationSeconds) || durationSeconds <= 0) return true;
  return durationSeconds < minSeconds;
}

/** Pure: ``true`` when ``value`` overflows a stable double-precision
 *  range for the seconds-axis. */
export function isNumericallyUnsafe(value: number): boolean {
  return !Number.isFinite(value) || Math.abs(value) > 1e15;
}
