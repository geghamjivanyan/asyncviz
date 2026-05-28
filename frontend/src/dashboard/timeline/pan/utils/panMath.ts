/**
 * Pure math helpers for pan calculations.
 */

import { SCALE_EPSILON_SECONDS } from "@/dashboard/timeline/scaling";

/** Pure: clamp a candidate ``timeStart`` so the resulting window
 *  ``[timeStart, timeStart + duration]`` stays inside ``[min, max]``.
 *  When either bound is ``null`` it is skipped. Returns the clamped
 *  ``timeStart``. */
export function clampTimeStart(
  timeStart: number,
  durationSeconds: number,
  minTimeSeconds: number | null,
  maxTimeSeconds: number | null,
): number {
  let start = timeStart;
  if (maxTimeSeconds !== null) {
    const maxStart = maxTimeSeconds - durationSeconds;
    if (start > maxStart) start = maxStart;
  }
  if (minTimeSeconds !== null) {
    if (start < minTimeSeconds) start = minTimeSeconds;
  }
  return start;
}

/** Pure: ``true`` when applying ``deltaSeconds`` would push past the
 *  configured bound. */
export function wouldExceedBound(
  timeStart: number,
  durationSeconds: number,
  deltaSeconds: number,
  minTimeSeconds: number | null,
  maxTimeSeconds: number | null,
): "min" | "max" | null {
  const nextStart = timeStart + deltaSeconds;
  if (minTimeSeconds !== null && nextStart < minTimeSeconds - SCALE_EPSILON_SECONDS) return "min";
  if (
    maxTimeSeconds !== null &&
    nextStart + durationSeconds > maxTimeSeconds + SCALE_EPSILON_SECONDS
  ) {
    return "max";
  }
  return null;
}

/** Pure: ``true`` when the viewport sits at the configured edge. */
export function atBoundEdge(
  timeStart: number,
  durationSeconds: number,
  minTimeSeconds: number | null,
  maxTimeSeconds: number | null,
): { atMin: boolean; atMax: boolean } {
  const tolerance = SCALE_EPSILON_SECONDS;
  const atMin =
    minTimeSeconds !== null && timeStart <= minTimeSeconds + tolerance;
  const atMax =
    maxTimeSeconds !== null && timeStart + durationSeconds >= maxTimeSeconds - tolerance;
  return { atMin, atMax };
}

/** Pure: compute the ``deltaSeconds`` that would center the viewport
 *  on ``targetSeconds``. */
export function deltaToCenter(
  targetSeconds: number,
  timeStart: number,
  durationSeconds: number,
): number {
  const targetStart = targetSeconds - durationSeconds / 2;
  return targetStart - timeStart;
}

/** Pure: compute the ``deltaSeconds`` that would move the viewport's
 *  left edge to ``targetTimeStartSeconds``. */
export function deltaToTimeStart(
  targetTimeStartSeconds: number,
  timeStart: number,
): number {
  return targetTimeStartSeconds - timeStart;
}
