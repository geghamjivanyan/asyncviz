/**
 * Pure grid-line resolver built on top of :func:`generateTicks`.
 *
 * Returns the *vertical* grid lines the renderer draws (one per
 * major + minor tick), separated so layers can paint majors with
 * higher contrast.
 */

import type { TimelineTickList } from "@/dashboard/timeline/scaling/models/TimelineScaleModels";

export interface TimelineScaleGridLines {
  majorXs: readonly number[];
  minorXs: readonly number[];
}

const EMPTY: TimelineScaleGridLines = Object.freeze({
  majorXs: Object.freeze([]) as readonly number[],
  minorXs: Object.freeze([]) as readonly number[],
});

/** Pure: split a tick list into major / minor x arrays. */
export function gridFromTicks(list: TimelineTickList): TimelineScaleGridLines {
  if (list.ticks.length === 0) return EMPTY;
  const majors: number[] = [];
  const minors: number[] = [];
  for (const tick of list.ticks) {
    if (tick.major) majors.push(tick.xCss);
    else minors.push(tick.xCss);
  }
  return { majorXs: majors, minorXs: minors };
}
