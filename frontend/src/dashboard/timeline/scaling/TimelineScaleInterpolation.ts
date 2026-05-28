/**
 * Pure interpolation primitives for the future animated-zoom
 * controller.
 *
 * The engine doesn't drive animation today — that responsibility
 * lives in a future task. But the math has to be deterministic +
 * replay-safe from day one, so we land the easing curves now and let
 * the controller pull them in unchanged.
 */

import type { ScaleInterpolationFrame } from "@/dashboard/timeline/scaling/models/TimelineScaleModels";

/** Pure: clamp ``t`` to ``[0, 1]``. */
export function clampPhase(t: number): number {
  if (!Number.isFinite(t)) return 0;
  if (t < 0) return 0;
  if (t > 1) return 1;
  return t;
}

/** Pure: linear easing. */
export function easeLinear(t: number): number {
  return clampPhase(t);
}

/** Pure: smoothstep easing — gentle start / gentle end. */
export function easeInOut(t: number): number {
  const c = clampPhase(t);
  return c * c * (3 - 2 * c);
}

/** Pure: cubic ease-out — fast start, decelerating finish. */
export function easeOutCubic(t: number): number {
  const c = clampPhase(t);
  return 1 - Math.pow(1 - c, 3);
}

/** Pure: interpolate one scale frame to another with a chosen easing. */
export function interpolateScaleFrame(
  frame: ScaleInterpolationFrame,
  ease: (t: number) => number = easeInOut,
): { timeStart: number; timeEnd: number } {
  const phase = ease(clampPhase(frame.t));
  return {
    timeStart: frame.fromTimeStart + (frame.toTimeStart - frame.fromTimeStart) * phase,
    timeEnd: frame.fromTimeEnd + (frame.toTimeEnd - frame.fromTimeEnd) * phase,
  };
}

/** Pure: produce N sample frames covering ``[0, 1]`` — used by tests
 *  and the future zoom controller's per-frame schedule. */
export function sampleInterpolation(
  steps: number,
  ease: (t: number) => number = easeInOut,
): number[] {
  if (steps <= 1) return [ease(1)];
  const out: number[] = [];
  for (let i = 0; i < steps; i += 1) {
    out.push(ease(i / (steps - 1)));
  }
  return out;
}
