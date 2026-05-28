import { describe, expect, it } from "vitest";
import {
  dragDeltaToSeconds,
  stepsToPanSeconds,
  wheelToPanSeconds,
} from "@/dashboard/timeline/pan/TimelinePanGestures";

describe("pan gestures", () => {
  it("dragDeltaToSeconds inverts the pointer delta", () => {
    expect(dragDeltaToSeconds(100, 0.01)).toBeCloseTo(-1);
    expect(dragDeltaToSeconds(-50, 0.01)).toBeCloseTo(0.5);
    expect(dragDeltaToSeconds(0, 0.01)).toBe(0);
  });

  it("wheelToPanSeconds defaults to the natural scale", () => {
    expect(wheelToPanSeconds(100, 0.01)).toBeCloseTo(1);
    expect(wheelToPanSeconds(-100, 0.01)).toBeCloseTo(-1);
  });

  it("wheelToPanSeconds honors the explicit knob when positive", () => {
    expect(
      wheelToPanSeconds(100, 0.01, {
        keyboardStepFraction: 0.1,
        shiftMultiplier: 2,
        wheelSecondsPerPixel: 0.05,
        velocityNoiseSecondsPerMs: 0,
      }),
    ).toBeCloseTo(5);
  });

  it("stepsToPanSeconds scales by viewport fraction", () => {
    expect(stepsToPanSeconds(1, 10)).toBeCloseTo(1.5);
    expect(stepsToPanSeconds(-1, 10)).toBeCloseTo(-1.5);
    expect(stepsToPanSeconds(0, 10)).toBe(0);
  });

  it("stepsToPanSeconds applies the shift multiplier", () => {
    expect(stepsToPanSeconds(1, 10, { shift: true })).toBeCloseTo(6);
  });
});
