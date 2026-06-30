/**
 * Pure helpers for working with :type:`ScaleConstraints`.
 */

import {
  DEFAULT_SCALE_CONSTRAINTS,
  type ScaleConstraints,
} from "@/dashboard/timeline/scaling/models/TimelineScaleModels";

export function mergeConstraints(
  base: ScaleConstraints = DEFAULT_SCALE_CONSTRAINTS,
  override: Partial<ScaleConstraints> = {},
): ScaleConstraints {
  return {
    minDurationSeconds: Math.max(
      Number.MIN_VALUE,
      override.minDurationSeconds ?? base.minDurationSeconds,
    ),
    maxDurationSeconds: Math.max(
      override.minDurationSeconds ?? base.minDurationSeconds,
      override.maxDurationSeconds ?? base.maxDurationSeconds,
    ),
    minTimeSeconds: override.minTimeSeconds ?? base.minTimeSeconds,
    maxTimeSeconds: override.maxTimeSeconds ?? base.maxTimeSeconds,
  };
}

/** Pure: ``true`` when the supplied duration is at one of the
 *  constraint edges (zoom-in or zoom-out stop). */
export function isAtConstraintEdge(
  durationSeconds: number,
  constraints: ScaleConstraints,
): "min" | "max" | null {
  if (durationSeconds <= constraints.minDurationSeconds) return "min";
  if (durationSeconds >= constraints.maxDurationSeconds) return "max";
  return null;
}

/** Pure: clamp a candidate duration into the constraint envelope. */
export function clampDuration(durationSeconds: number, constraints: ScaleConstraints): number {
  if (!Number.isFinite(durationSeconds) || durationSeconds <= 0) {
    return constraints.minDurationSeconds;
  }
  if (durationSeconds < constraints.minDurationSeconds) return constraints.minDurationSeconds;
  if (durationSeconds > constraints.maxDurationSeconds) return constraints.maxDurationSeconds;
  return durationSeconds;
}
