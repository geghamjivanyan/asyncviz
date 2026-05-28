import { describe, expect, it } from "vitest";
import {
  atBoundEdge,
  clampTimeStart,
  deltaToCenter,
  deltaToTimeStart,
  wouldExceedBound,
} from "@/dashboard/timeline/pan/utils/panMath";

describe("panMath", () => {
  it("clampTimeStart respects max bound", () => {
    expect(clampTimeStart(15, 10, null, 20)).toBe(10);
    expect(clampTimeStart(5, 10, null, 20)).toBe(5);
  });

  it("clampTimeStart respects min bound", () => {
    expect(clampTimeStart(-5, 10, 0, null)).toBe(0);
    expect(clampTimeStart(2, 10, 0, null)).toBe(2);
  });

  it("clampTimeStart docks the window at the right edge when over-shot", () => {
    // duration=10 window cannot start past 20-10=10
    expect(clampTimeStart(50, 10, 0, 20)).toBe(10);
  });

  it("wouldExceedBound flags min/max breaches", () => {
    expect(wouldExceedBound(0, 10, -1, 0, 20)).toBe("min");
    expect(wouldExceedBound(10, 10, 5, 0, 20)).toBe("max");
    expect(wouldExceedBound(5, 10, 1, 0, 20)).toBeNull();
  });

  it("atBoundEdge detects edges within tolerance", () => {
    expect(atBoundEdge(0, 10, 0, 20).atMin).toBe(true);
    expect(atBoundEdge(10, 10, 0, 20).atMax).toBe(true);
    expect(atBoundEdge(5, 10, 0, 20).atMin).toBe(false);
  });

  it("deltaToCenter targets the requested time", () => {
    expect(deltaToCenter(10, 0, 10)).toBe(5);
  });

  it("deltaToTimeStart targets the requested timeStart", () => {
    expect(deltaToTimeStart(15, 10)).toBe(5);
  });
});
