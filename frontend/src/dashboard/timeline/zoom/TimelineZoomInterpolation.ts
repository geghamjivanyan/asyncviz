/**
 * Re-export of the scale engine's interpolation primitives, scoped
 * to the controller's idiom.
 *
 * The controller doesn't drive animated zoom today (that's the next
 * task), but the math has to land deterministically so the future
 * animation controller plugs in unchanged.
 */

import {
  easeLinear,
  easeOutCubic,
  interpolateScaleFrame,
  sampleInterpolation,
  scaleEaseInOut,
  type ScaleInterpolationFrame,
} from "@/dashboard/timeline/scaling";

export {
  easeLinear as zoomEaseLinear,
  easeOutCubic as zoomEaseOutCubic,
  scaleEaseInOut as zoomEaseInOut,
  interpolateScaleFrame as zoomInterpolate,
  sampleInterpolation as zoomSamplePhases,
  type ScaleInterpolationFrame as ZoomInterpolationFrame,
};

/** Pure: interpolate between two ``[start, end]`` ranges with the
 *  chosen easing. */
export function interpolateZoomRange(args: {
  fromStart: number;
  fromEnd: number;
  toStart: number;
  toEnd: number;
  t: number;
  ease?: (t: number) => number;
}): { startSeconds: number; endSeconds: number } {
  const frame: ScaleInterpolationFrame = {
    fromTimeStart: args.fromStart,
    fromTimeEnd: args.fromEnd,
    toTimeStart: args.toStart,
    toTimeEnd: args.toEnd,
    t: args.t,
  };
  const result = interpolateScaleFrame(frame, args.ease);
  return { startSeconds: result.timeStart, endSeconds: result.timeEnd };
}
