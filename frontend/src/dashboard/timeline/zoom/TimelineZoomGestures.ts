/**
 * Pure gesture-to-factor primitives.
 *
 * The controller doesn't bind DOM events itself — that's a future
 * task — but the math has to land deterministically today so the
 * future wheel / pinch controller plugs in without recomputing
 * anything.
 *
 * Wheel semantics:
 *
 *   * trackpad pinch + Ctrl-wheel emit ``deltaY`` in pixel mode,
 *   * mouse wheel emits ``deltaY`` in line mode (≈16px per line),
 *   * page mode (rare) emits ``deltaY`` in viewport heights.
 *
 * The helpers normalize all three modes to a comparable factor.
 */

import { DEFAULT_ZOOM_CONFIG, type ZoomConfig } from "@/dashboard/timeline/zoom/models/TimelineZoomModels";

export type WheelDeltaMode = "pixel" | "line" | "page";

export interface WheelGestureInput {
  deltaY: number;
  deltaMode: WheelDeltaMode;
}

/** Pure: convert a normalized wheel delta into a zoom factor.
 *  ``deltaY > 0`` zooms out, ``< 0`` zooms in — matches the standard
 *  trackpad pinch convention. */
export function wheelToZoomFactor(
  input: WheelGestureInput,
  config: ZoomConfig = DEFAULT_ZOOM_CONFIG,
): number {
  if (!Number.isFinite(input.deltaY) || input.deltaY === 0) return 1;
  const pixels = normalizeWheelDelta(input, config);
  const scale = input.deltaMode === "pixel" ? config.wheelPixelScale : config.wheelFactorScale;
  return Math.exp(pixels * scale);
}

/** Pure: convert a pinch ratio (typical 0.5 .. 2.0) to a zoom factor.
 *  The function is the identity today — separated so the future
 *  inertial controller can swap in a damped curve. */
export function pinchToZoomFactor(ratio: number): number {
  if (!Number.isFinite(ratio) || ratio <= 0) return 1;
  return 1 / ratio;
}

/** Pure: convert a normalized step (number of "clicks") into a zoom
 *  factor using the controller's step factor. ``steps > 0`` zooms out,
 *  ``< 0`` zooms in — matches keyboard semantics. */
export function stepsToZoomFactor(
  steps: number,
  config: ZoomConfig = DEFAULT_ZOOM_CONFIG,
): number {
  if (!Number.isFinite(steps) || steps === 0) return 1;
  const factor = config.stepFactor;
  if (steps > 0) return Math.pow(1 / factor, steps);
  return Math.pow(factor, -steps);
}

function normalizeWheelDelta(input: WheelGestureInput, config: ZoomConfig): number {
  switch (input.deltaMode) {
    case "pixel":
      return input.deltaY;
    case "line":
      return input.deltaY * config.wheelLinePx;
    case "page":
      return input.deltaY * 800;
  }
}
