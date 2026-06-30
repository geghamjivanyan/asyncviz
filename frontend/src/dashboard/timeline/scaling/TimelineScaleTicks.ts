/**
 * Dynamic, zoom-aware tick generation for the time axis.
 *
 * Tick spacing climbs through a deterministic ladder so the visible
 * label density stays stable across zoom transitions: 1µs → 5µs →
 * 10µs → … → 1ms → 5ms → … → 1s → 5s → 30s → 1m → 1h, etc.
 *
 * The generator emits one major tick per "level" plus
 * ``minorRatio - 1`` minor ticks per gap. Minor ticks are unlabeled.
 *
 * The function is pure so the engine can cache its output keyed on
 * the active scale.
 */

import { formatTickLabel, pickTickInterval } from "@/dashboard/timeline/utils/ticks";
import type { TimelineTimeScale } from "@/dashboard/timeline/scaling/TimelineTimeScale";
import type {
  TimelineScaleTick,
  TimelineTickList,
} from "@/dashboard/timeline/scaling/models/TimelineScaleModels";

export interface GenerateTicksOptions {
  /** Target pixel spacing between major ticks. */
  targetMajorSpacingPx?: number;
  /** Number of minor steps between major ticks (default 5). */
  minorRatio?: number;
  /** Upper cap on emitted ticks — defensive against pathological
   *  scale + width combinations. */
  maxTicks?: number;
}

const DEFAULTS = {
  targetMajorSpacingPx: 80,
  minorRatio: 5,
  maxTicks: 4096,
};

/** Pure: build a deterministic tick list for ``scale``. */
export function generateTicks(
  scale: TimelineTimeScale,
  options: GenerateTicksOptions = {},
): TimelineTickList {
  const targetMajor = Math.max(8, options.targetMajorSpacingPx ?? DEFAULTS.targetMajorSpacingPx);
  const minorRatio = Math.max(1, Math.floor(options.minorRatio ?? DEFAULTS.minorRatio));
  const maxTicks = Math.max(8, options.maxTicks ?? DEFAULTS.maxTicks);

  const majorInterval = pickTickInterval(scale.durationSeconds, scale.widthPx, targetMajor);
  const minorInterval = majorInterval / minorRatio;
  const ticks: TimelineScaleTick[] = [];

  const firstMinor = Math.ceil(scale.timeStart / minorInterval) * minorInterval;
  for (let t = firstMinor, i = 0; t <= scale.timeEnd && i < maxTicks; t += minorInterval, i += 1) {
    // Round the candidate to the nearest minor step to keep floating-
    // point drift from accumulating across many additions.
    const rounded = Math.round(t / minorInterval) * minorInterval;
    const xCss = scale.timeToX(rounded);
    const major = isApproximatelyMultiple(rounded, majorInterval);
    ticks.push({
      timeSeconds: rounded,
      xCss,
      major,
      label: major ? formatTickLabel(rounded, majorInterval) : null,
    });
  }
  return {
    ticks,
    majorIntervalSeconds: majorInterval,
    minorIntervalSeconds: minorInterval,
    key: scale.key,
  };
}

function isApproximatelyMultiple(value: number, modulus: number): boolean {
  if (modulus <= 0) return false;
  const ratio = value / modulus;
  return Math.abs(ratio - Math.round(ratio)) < 1e-6;
}
