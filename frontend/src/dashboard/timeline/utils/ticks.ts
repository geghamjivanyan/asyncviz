/**
 * Tick-density helpers.
 *
 * Pure math — the grid layer calls :func:`pickTickInterval` once per
 * frame to pick a "nice" tick interval at the current zoom level.
 *
 * The chosen interval guarantees that ticks are at least
 * ``targetSpacingPx`` apart so the grid stays readable.
 */

const PRESET_INTERVALS_SECONDS = [
  0.000001, 0.000005, 0.00001, 0.00005, 0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1,
  2, 5, 10, 30, 60, 300, 600, 1800, 3600, 7200, 14400, 28800, 86400,
];

/** Pure: pick the smallest "nice" interval such that ticks are at
 *  least ``targetSpacingPx`` apart. */
export function pickTickInterval(
  durationSeconds: number,
  widthPx: number,
  targetSpacingPx: number,
): number {
  if (durationSeconds <= 0 || widthPx <= 0 || targetSpacingPx <= 0) {
    return PRESET_INTERVALS_SECONDS[0]!;
  }
  const pixelsPerSecond = widthPx / durationSeconds;
  const minIntervalSeconds = targetSpacingPx / pixelsPerSecond;
  for (const interval of PRESET_INTERVALS_SECONDS) {
    if (interval >= minIntervalSeconds) return interval;
  }
  return PRESET_INTERVALS_SECONDS[PRESET_INTERVALS_SECONDS.length - 1]!;
}

/** Pure: format a tick label for the current interval — sub-second
 *  intervals get millisecond precision; everything else gets seconds. */
export function formatTickLabel(value: number, intervalSeconds: number): string {
  if (!Number.isFinite(value)) return "—";
  if (intervalSeconds < 1) {
    if (intervalSeconds < 0.001) return `${(value * 1_000_000).toFixed(0)}µs`;
    return `${(value * 1000).toFixed(0)}ms`;
  }
  if (intervalSeconds < 60) return `${value.toFixed(2)}s`;
  const minutes = Math.floor(value / 60);
  const secs = value % 60;
  return `${minutes}m${secs.toFixed(0).padStart(2, "0")}s`;
}
