import { describe, expect, it } from "vitest";
import {
  guardScaleBounds,
  isNearPrecisionFloor,
} from "@/dashboard/timeline/scaling/TimelineScalePrecision";
import { DEFAULT_SCALE_CONSTRAINTS } from "@/dashboard/timeline/scaling/models/TimelineScaleModels";

describe("guardScaleBounds", () => {
  it("returns unchanged bounds when inside the envelope", () => {
    const result = guardScaleBounds(0, 5, DEFAULT_SCALE_CONSTRAINTS);
    expect(result.timeStart).toBe(0);
    expect(result.timeEnd).toBe(5);
    expect(result.adjusted).toBe(false);
  });

  it("widens too-small windows to the min duration", () => {
    const c = { ...DEFAULT_SCALE_CONSTRAINTS, minDurationSeconds: 1 };
    const result = guardScaleBounds(0, 0.1, c);
    expect(result.timeEnd).toBeCloseTo(1);
    expect(result.adjusted).toBe(true);
    expect(result.reason).toBe("duration-too-small");
  });

  it("narrows too-large windows to the max duration", () => {
    const c = { ...DEFAULT_SCALE_CONSTRAINTS, maxDurationSeconds: 10 };
    const result = guardScaleBounds(0, 1000, c);
    expect(result.timeEnd).toBeCloseTo(10);
    expect(result.reason).toBe("duration-too-large");
  });

  it("shifts the window to respect the minTime constraint", () => {
    const c = { ...DEFAULT_SCALE_CONSTRAINTS, minTimeSeconds: 5 };
    const result = guardScaleBounds(0, 3, c);
    expect(result.timeStart).toBeCloseTo(5);
    expect(result.timeEnd).toBeCloseTo(8);
  });

  it("resets non-finite inputs", () => {
    const result = guardScaleBounds(NaN, Infinity, DEFAULT_SCALE_CONSTRAINTS);
    expect(result.adjusted).toBe(true);
    expect(result.reason).toBe("non-finite");
  });
});

describe("isNearPrecisionFloor", () => {
  it("flags sub-microsecond per pixel as near the floor", () => {
    expect(isNearPrecisionFloor(1e-10, 1000)).toBe(true);
  });

  it("returns false for normal zoom levels", () => {
    expect(isNearPrecisionFloor(10, 1000)).toBe(false);
  });
});
