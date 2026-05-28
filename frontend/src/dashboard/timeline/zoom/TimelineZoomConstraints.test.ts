import { describe, expect, it } from "vitest";
import {
  checkDurationAgainstConstraints,
  wouldBreachConstraints,
} from "@/dashboard/timeline/zoom/TimelineZoomConstraints";
import { DEFAULT_SCALE_CONSTRAINTS } from "@/dashboard/timeline/scaling";

describe("zoom constraints", () => {
  const constraints = {
    ...DEFAULT_SCALE_CONSTRAINTS,
    minDurationSeconds: 1,
    maxDurationSeconds: 100,
  };

  it("atMin / atMax flags fire at the envelope edges", () => {
    expect(checkDurationAgainstConstraints(1, constraints).atMin).toBe(true);
    expect(checkDurationAgainstConstraints(100, constraints).atMax).toBe(true);
    const middle = checkDurationAgainstConstraints(10, constraints);
    expect(middle.atMin).toBe(false);
    expect(middle.atMax).toBe(false);
  });

  it("wouldBreachConstraints detects min/max breaches", () => {
    expect(wouldBreachConstraints(2, 0.1, constraints)).toBe("min");
    expect(wouldBreachConstraints(50, 10, constraints)).toBe("max");
    expect(wouldBreachConstraints(10, 1.5, constraints)).toBeNull();
  });

  it("wouldBreachConstraints returns null for invalid factors", () => {
    expect(wouldBreachConstraints(10, 0, constraints)).toBeNull();
    expect(wouldBreachConstraints(10, -1, constraints)).toBeNull();
  });
});
