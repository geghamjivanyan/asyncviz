import { describe, expect, it } from "vitest";
import {
  interpolatePanTimeStart,
  panEaseInOut,
  panEaseLinear,
  panEaseOutCubic,
} from "@/dashboard/timeline/pan/TimelinePanInterpolation";

describe("pan interpolation", () => {
  it("easing curves boundary-correct (0 → 0, 1 → 1)", () => {
    for (const fn of [panEaseLinear, panEaseInOut, panEaseOutCubic]) {
      expect(fn(0)).toBeCloseTo(0);
      expect(fn(1)).toBeCloseTo(1);
    }
  });

  it("interpolatePanTimeStart linearly blends start values", () => {
    expect(
      interpolatePanTimeStart({ fromStart: 0, toStart: 10, t: 0.5, ease: panEaseLinear }),
    ).toBeCloseTo(5);
  });

  it("interpolatePanTimeStart clamps phase outside [0, 1]", () => {
    expect(
      interpolatePanTimeStart({ fromStart: 0, toStart: 10, t: -1, ease: panEaseLinear }),
    ).toBeCloseTo(0);
    expect(
      interpolatePanTimeStart({ fromStart: 0, toStart: 10, t: 2, ease: panEaseLinear }),
    ).toBeCloseTo(10);
  });
});
