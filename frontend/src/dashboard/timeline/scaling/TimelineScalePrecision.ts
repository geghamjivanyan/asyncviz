/**
 * Precision-safe helpers for the time-scaling engine.
 *
 * Floating-point math degrades around the extremes — sub-microsecond
 * zoom + hour-long replays both push the precision budget. The helpers
 * here are conservative checks the engine can call before committing
 * to a transform.
 */

import {
  SCALE_EPSILON_SECONDS,
  isNumericallyUnsafe,
} from "@/dashboard/timeline/scaling/utils/numerics";
import type { ScaleConstraints } from "@/dashboard/timeline/scaling/models/TimelineScaleModels";

export interface PrecisionGuardResult {
  /** Adjusted ``timeStart`` after the guard. */
  timeStart: number;
  /** Adjusted ``timeEnd`` after the guard. */
  timeEnd: number;
  /** ``true`` when the input was sanitized. */
  adjusted: boolean;
  /** Adjustment reason — used in trace messages. */
  reason: "none" | "duration-too-small" | "duration-too-large" | "non-finite";
}

/**
 * Pure: clamp ``[timeStart, timeEnd]`` so the resulting duration sits
 * inside the constraint envelope, the start respects the lower bound,
 * and both bounds are finite. The function is conservative — it only
 * touches values that need touching.
 */
export function guardScaleBounds(
  timeStart: number,
  timeEnd: number,
  constraints: ScaleConstraints,
): PrecisionGuardResult {
  if (
    isNumericallyUnsafe(timeStart) ||
    isNumericallyUnsafe(timeEnd) ||
    !Number.isFinite(timeStart) ||
    !Number.isFinite(timeEnd)
  ) {
    return {
      timeStart: 0,
      timeEnd: constraints.minDurationSeconds,
      adjusted: true,
      reason: "non-finite",
    };
  }
  let start = timeStart;
  let end = timeEnd;
  let adjusted = false;
  let reason: PrecisionGuardResult["reason"] = "none";
  let duration = end - start;
  if (duration < constraints.minDurationSeconds) {
    end = start + constraints.minDurationSeconds;
    duration = constraints.minDurationSeconds;
    adjusted = true;
    reason = "duration-too-small";
  }
  if (duration > constraints.maxDurationSeconds) {
    end = start + constraints.maxDurationSeconds;
    duration = constraints.maxDurationSeconds;
    adjusted = true;
    reason = "duration-too-large";
  }
  if (constraints.minTimeSeconds !== null && start < constraints.minTimeSeconds) {
    const shift = constraints.minTimeSeconds - start;
    start += shift;
    end += shift;
    adjusted = true;
  }
  if (constraints.maxTimeSeconds !== null && end > constraints.maxTimeSeconds) {
    const shift = end - constraints.maxTimeSeconds;
    start -= shift;
    end -= shift;
    adjusted = true;
  }
  if (end - start < SCALE_EPSILON_SECONDS) {
    end = start + SCALE_EPSILON_SECONDS;
    adjusted = true;
    if (reason === "none") reason = "duration-too-small";
  }
  return { timeStart: start, timeEnd: end, adjusted, reason };
}

/**
 * Pure: return ``true`` when the supplied scale parameters approach
 * the precision floor (sub-millisecond per pixel) and the engine
 * should warn the diagnostics surface.
 */
export function isNearPrecisionFloor(
  durationSeconds: number,
  widthPx: number,
): boolean {
  if (widthPx <= 0) return true;
  const secondsPerPixel = durationSeconds / widthPx;
  return secondsPerPixel < 1e-6;
}
