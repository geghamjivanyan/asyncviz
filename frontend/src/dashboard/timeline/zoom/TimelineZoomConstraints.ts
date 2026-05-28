/**
 * Pure helpers that adapt the scale-engine's constraints into the
 * zoom controller's idiom.
 *
 * The controller never invents its own min/max — it always defers to
 * :type:`ScaleConstraints`. These helpers exist so call sites can ask
 * "what's the limiting factor right now?" without rereading the
 * engine's internals.
 */

import type { ScaleConstraints } from "@/dashboard/timeline/scaling";

export interface ConstraintCheck {
  /** Allowed minimum duration the next call may produce. */
  minDurationSeconds: number;
  /** Allowed maximum duration the next call may produce. */
  maxDurationSeconds: number;
  /** Does the candidate sit at or below the min? */
  atMin: boolean;
  /** Does the candidate sit at or above the max? */
  atMax: boolean;
}

/** Pure: check a candidate duration against the constraint envelope. */
export function checkDurationAgainstConstraints(
  durationSeconds: number,
  constraints: ScaleConstraints,
): ConstraintCheck {
  return {
    minDurationSeconds: constraints.minDurationSeconds,
    maxDurationSeconds: constraints.maxDurationSeconds,
    atMin: durationSeconds <= constraints.minDurationSeconds * (1 + 1e-9),
    atMax: durationSeconds >= constraints.maxDurationSeconds * (1 - 1e-9),
  };
}

/** Pure: ``true`` when applying ``factor`` to ``currentDuration``
 *  would push past the constraint envelope. The controller uses this
 *  to suppress no-op invalidations at the constraint edges. */
export function wouldBreachConstraints(
  currentDurationSeconds: number,
  factor: number,
  constraints: ScaleConstraints,
): "min" | "max" | null {
  if (!Number.isFinite(factor) || factor <= 0) return null;
  const next = currentDurationSeconds * factor;
  if (factor < 1 && next < constraints.minDurationSeconds) return "min";
  if (factor > 1 && next > constraints.maxDurationSeconds) return "max";
  return null;
}
