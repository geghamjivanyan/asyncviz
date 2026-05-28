/**
 * Pure interpolation primitives for the future smooth-pan
 * controller.
 *
 * The controller doesn't drive smooth scrolling today; the math
 * lives here so the future hook plugs in unchanged.
 */

import {
  zoomEaseInOut,
  zoomEaseLinear,
  zoomEaseOutCubic,
} from "@/dashboard/timeline/zoom";

export {
  zoomEaseInOut as panEaseInOut,
  zoomEaseLinear as panEaseLinear,
  zoomEaseOutCubic as panEaseOutCubic,
};

/** Pure: interpolate between two ``timeStart`` values. */
export function interpolatePanTimeStart(args: {
  fromStart: number;
  toStart: number;
  t: number;
  ease?: (t: number) => number;
}): number {
  const ease = args.ease ?? zoomEaseInOut;
  const clamped = Math.max(0, Math.min(1, Number.isFinite(args.t) ? args.t : 0));
  const phase = ease(clamped);
  return args.fromStart + (args.toStart - args.fromStart) * phase;
}
