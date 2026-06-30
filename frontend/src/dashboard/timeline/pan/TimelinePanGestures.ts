/**
 * Pure gesture-to-seconds primitives.
 *
 * Pan gestures arrive in three shapes — pointer drag deltas (CSS
 * pixels), horizontal wheel deltas (CSS pixels), and keyboard arrow
 * steps. Each shape gets a pure converter the controller calls.
 */

import {
  DEFAULT_PAN_CONFIG,
  type PanConfig,
} from "@/dashboard/timeline/pan/models/TimelinePanModels";

/** Pure: convert a pixel-space drag delta to a world-time delta.
 *  ``deltaXPx > 0`` means the pointer moved right; the viewport
 *  should move *left* (i.e. ``timeStart`` decreases). */
export function dragDeltaToSeconds(deltaXPx: number, secondsPerPixel: number): number {
  if (!Number.isFinite(deltaXPx) || !Number.isFinite(secondsPerPixel)) return 0;
  if (deltaXPx === 0 || secondsPerPixel === 0) return 0;
  return -deltaXPx * secondsPerPixel;
}

/** Pure: convert a horizontal wheel delta to a world-time delta.
 *  Trackpad two-finger horizontal scrolling emits ``deltaX`` in pixel
 *  mode; mouse wheels with horizontal axes emit it in line mode. The
 *  ``config.wheelSecondsPerPixel`` knob lets users tune the scale. */
export function wheelToPanSeconds(
  deltaXPx: number,
  secondsPerPixel: number,
  config: PanConfig = DEFAULT_PAN_CONFIG,
): number {
  if (!Number.isFinite(deltaXPx) || deltaXPx === 0) return 0;
  if (secondsPerPixel === 0) return 0;
  // ``wheelSecondsPerPixel`` falls back to the natural scale when
  // unset (zero or non-positive) so trackpad pans feel 1:1.
  const scale = config.wheelSecondsPerPixel > 0 ? config.wheelSecondsPerPixel : secondsPerPixel;
  return deltaXPx * scale;
}

/** Pure: convert a keyboard step (``-1`` = pan left, ``+1`` = pan
 *  right) to a world-time delta. ``shift`` multiplies the step by
 *  ``config.shiftMultiplier`` so power users move further per press. */
export function stepsToPanSeconds(
  steps: number,
  durationSeconds: number,
  options: { shift?: boolean; config?: PanConfig } = {},
): number {
  if (!Number.isFinite(steps) || steps === 0) return 0;
  const config = options.config ?? DEFAULT_PAN_CONFIG;
  const fraction = config.keyboardStepFraction;
  const multiplier = options.shift ? config.shiftMultiplier : 1;
  return steps * durationSeconds * fraction * multiplier;
}
