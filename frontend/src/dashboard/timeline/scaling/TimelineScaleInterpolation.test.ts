import { describe, expect, it } from "vitest";
import {
  easeInOut,
  easeLinear,
  easeOutCubic,
  interpolateScaleFrame,
  sampleInterpolation,
  clampPhase,
} from "@/dashboard/timeline/scaling/TimelineScaleInterpolation";

describe("scale interpolation", () => {
  it("clampPhase forces t into [0, 1]", () => {
    expect(clampPhase(-0.5)).toBe(0);
    expect(clampPhase(1.5)).toBe(1);
    expect(clampPhase(0.4)).toBe(0.4);
    expect(clampPhase(NaN)).toBe(0);
  });

  it("easing curves start at 0 and finish at 1", () => {
    for (const fn of [easeLinear, easeInOut, easeOutCubic]) {
      expect(fn(0)).toBeCloseTo(0);
      expect(fn(1)).toBeCloseTo(1);
    }
  });

  it("interpolateScaleFrame blends start + end with the chosen ease", () => {
    const linear = interpolateScaleFrame(
      { fromTimeStart: 0, fromTimeEnd: 10, toTimeStart: 10, toTimeEnd: 20, t: 0.5 },
      easeLinear,
    );
    expect(linear.timeStart).toBeCloseTo(5);
    expect(linear.timeEnd).toBeCloseTo(15);
  });

  it("sampleInterpolation returns deterministic phase samples", () => {
    const samples = sampleInterpolation(5, easeLinear);
    expect(samples).toEqual([0, 0.25, 0.5, 0.75, 1]);
  });
});
