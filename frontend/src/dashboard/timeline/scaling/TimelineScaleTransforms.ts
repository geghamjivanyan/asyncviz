/**
 * Pure transform helpers built on top of :class:`TimelineTimeScale`.
 *
 * These helpers are the "named convenience" wrappers around the
 * scale's own ``timeToX`` / ``xToTime``. Keeping them in their own
 * file means callers can import the specific transform they need
 * without depending on the whole engine.
 */

import type { TimelineTimeScale } from "@/dashboard/timeline/scaling/TimelineTimeScale";

/** Pure: world seconds → CSS pixel x. */
export function timeToScreenX(scale: TimelineTimeScale, seconds: number): number {
  return scale.timeToX(seconds);
}

/** Pure: CSS pixel x → world seconds. */
export function screenXToTime(scale: TimelineTimeScale, xCss: number): number {
  return scale.xToTime(xCss);
}

/** Pure: pan the scale window by ``deltaSeconds``. */
export function panScale(
  scale: TimelineTimeScale,
  deltaSeconds: number,
): { timeStart: number; timeEnd: number } {
  return {
    timeStart: scale.timeStart + deltaSeconds,
    timeEnd: scale.timeEnd + deltaSeconds,
  };
}

/**
 * Pure: zoom a scale around an anchor in world seconds. ``factor < 1``
 * zooms in; ``factor > 1`` zooms out. Anchor stays at the same
 * fractional position inside the new window.
 */
export function zoomScaleAroundTime(
  scale: TimelineTimeScale,
  anchorSeconds: number,
  factor: number,
): { timeStart: number; timeEnd: number } {
  if (!Number.isFinite(factor) || factor <= 0) {
    return { timeStart: scale.timeStart, timeEnd: scale.timeEnd };
  }
  const nextDuration = scale.durationSeconds * factor;
  const t = (anchorSeconds - scale.timeStart) / scale.durationSeconds;
  const nextStart = anchorSeconds - t * nextDuration;
  const nextEnd = nextStart + nextDuration;
  return { timeStart: nextStart, timeEnd: nextEnd };
}

/** Pure: zoom a scale around a CSS pixel anchor. */
export function zoomScaleAroundX(
  scale: TimelineTimeScale,
  xCss: number,
  factor: number,
): { timeStart: number; timeEnd: number } {
  return zoomScaleAroundTime(scale, scale.xToTime(xCss), factor);
}

/** Pure: fit a scale so it spans ``[start, end]`` exactly. */
export function fitScaleToRange(
  scale: TimelineTimeScale,
  startSeconds: number,
  endSeconds: number,
): { timeStart: number; timeEnd: number } {
  if (!(endSeconds > startSeconds)) {
    return { timeStart: scale.timeStart, timeEnd: scale.timeEnd };
  }
  return { timeStart: startSeconds, timeEnd: endSeconds };
}
