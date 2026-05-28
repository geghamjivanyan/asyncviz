import { describe, expect, it } from "vitest";
import { normalizeViewport } from "@/dashboard/timeline/scaling/TimelineScaleNormalization";
import { DEFAULT_SCALE_CONSTRAINTS } from "@/dashboard/timeline/scaling/models/TimelineScaleModels";

describe("normalizeViewport", () => {
  it("returns the input unchanged when inside the constraint envelope", () => {
    const result = normalizeViewport({
      timeStart: 0,
      timeEnd: 5,
      widthPx: 800,
      devicePixelRatio: 1,
      constraints: DEFAULT_SCALE_CONSTRAINTS,
    });
    expect(result.timeStart).toBe(0);
    expect(result.timeEnd).toBe(5);
    expect(result.adjusted).toBe(false);
    expect(result.widthPx).toBe(800);
  });

  it("flags precision-floor warnings for sub-microsecond zoom", () => {
    const result = normalizeViewport({
      timeStart: 0,
      timeEnd: 1e-9,
      widthPx: 800,
      devicePixelRatio: 1,
      constraints: { ...DEFAULT_SCALE_CONSTRAINTS, minDurationSeconds: 1e-10 },
    });
    expect(result.nearPrecisionFloor).toBe(true);
  });

  it("snaps width to the device-pixel grid", () => {
    const result = normalizeViewport({
      timeStart: 0,
      timeEnd: 1,
      widthPx: 123.7,
      devicePixelRatio: 2,
      constraints: DEFAULT_SCALE_CONSTRAINTS,
    });
    expect(result.widthPx).toBeCloseTo(123.5);
  });
});
