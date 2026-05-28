import { describe, expect, it } from "vitest";
import {
  clampDuration,
  isAtConstraintEdge,
  mergeConstraints,
} from "@/dashboard/timeline/scaling/TimelineScaleConstraints";
import { DEFAULT_SCALE_CONSTRAINTS } from "@/dashboard/timeline/scaling/models/TimelineScaleModels";

describe("scale constraints", () => {
  it("mergeConstraints fills in missing fields from the base", () => {
    const merged = mergeConstraints(DEFAULT_SCALE_CONSTRAINTS, {
      minDurationSeconds: 0.5,
    });
    expect(merged.minDurationSeconds).toBe(0.5);
    expect(merged.maxDurationSeconds).toBe(DEFAULT_SCALE_CONSTRAINTS.maxDurationSeconds);
  });

  it("mergeConstraints prevents max from dropping below min", () => {
    const merged = mergeConstraints(DEFAULT_SCALE_CONSTRAINTS, {
      minDurationSeconds: 10,
      maxDurationSeconds: 1,
    });
    expect(merged.maxDurationSeconds).toBe(10);
  });

  it("isAtConstraintEdge detects min + max edges", () => {
    expect(isAtConstraintEdge(0.5, { ...DEFAULT_SCALE_CONSTRAINTS, minDurationSeconds: 1 })).toBe(
      "min",
    );
    expect(isAtConstraintEdge(5, { ...DEFAULT_SCALE_CONSTRAINTS, maxDurationSeconds: 5 })).toBe(
      "max",
    );
    expect(isAtConstraintEdge(2, DEFAULT_SCALE_CONSTRAINTS)).toBeNull();
  });

  it("clampDuration handles invalid + out-of-range inputs", () => {
    const c = { ...DEFAULT_SCALE_CONSTRAINTS, minDurationSeconds: 1, maxDurationSeconds: 10 };
    expect(clampDuration(0, c)).toBe(1);
    expect(clampDuration(20, c)).toBe(10);
    expect(clampDuration(5, c)).toBe(5);
    expect(clampDuration(NaN, c)).toBe(1);
  });
});
