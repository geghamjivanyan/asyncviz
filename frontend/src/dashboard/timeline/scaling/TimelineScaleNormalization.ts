/**
 * Pure viewport-normalization helpers.
 *
 * Normalization is the bridge between raw user input (a wheel
 * delta, a drag) and the engine's strict, constraint-respecting
 * scale snapshot. The helpers here clamp, round, and snap so
 * downstream code never has to second-guess the floating-point
 * shape of the camera state.
 */

import { snapToPixel } from "@/dashboard/timeline/scaling/utils/numerics";
import {
  guardScaleBounds,
  isNearPrecisionFloor,
  type PrecisionGuardResult,
} from "@/dashboard/timeline/scaling/TimelineScalePrecision";
import type { ScaleConstraints } from "@/dashboard/timeline/scaling/models/TimelineScaleModels";

export interface NormalizeViewportArgs {
  timeStart: number;
  timeEnd: number;
  widthPx: number;
  devicePixelRatio: number;
  constraints: ScaleConstraints;
}

export interface NormalizeViewportResult extends PrecisionGuardResult {
  widthPx: number;
  /** ``true`` when the engine should warn about precision loss. */
  nearPrecisionFloor: boolean;
}

/** Pure: enforce constraints + snap the visible window to a stable
 *  shape for downstream consumers. */
export function normalizeViewport(args: NormalizeViewportArgs): NormalizeViewportResult {
  const guarded = guardScaleBounds(args.timeStart, args.timeEnd, args.constraints);
  const widthPx = snapToPixel(Math.max(1, args.widthPx), args.devicePixelRatio);
  const nearPrecisionFloor = isNearPrecisionFloor(guarded.timeEnd - guarded.timeStart, widthPx);
  return {
    ...guarded,
    widthPx,
    nearPrecisionFloor,
  };
}
