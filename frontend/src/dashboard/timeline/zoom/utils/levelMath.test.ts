import { describe, expect, it } from "vitest";
import {
  durationToLevel,
  factorFromLevelDelta,
  levelToDuration,
} from "@/dashboard/timeline/zoom/utils/levelMath";

const bounds = { minDurationSeconds: 0.001, maxDurationSeconds: 1000 };

describe("levelMath", () => {
  it("maps the max duration to level 0 and the min duration to level 1", () => {
    expect(durationToLevel(bounds.maxDurationSeconds, bounds)).toBeCloseTo(0);
    expect(durationToLevel(bounds.minDurationSeconds, bounds)).toBeCloseTo(1);
  });

  it("clamps out-of-range durations", () => {
    expect(durationToLevel(bounds.maxDurationSeconds * 10, bounds)).toBeCloseTo(0);
    expect(durationToLevel(bounds.minDurationSeconds * 0.1, bounds)).toBeCloseTo(1);
  });

  it("level → duration is the inverse of duration → level", () => {
    for (const d of [0.01, 0.1, 1, 10, 100]) {
      const level = durationToLevel(d, bounds);
      expect(levelToDuration(level, bounds)).toBeCloseTo(d, 6);
    }
  });

  it("factorFromLevelDelta produces meaningful zoom factors", () => {
    const inFactor = factorFromLevelDelta(10, 0.1, bounds);
    expect(inFactor).toBeLessThan(1);
    const outFactor = factorFromLevelDelta(10, -0.1, bounds);
    expect(outFactor).toBeGreaterThan(1);
  });

  it("level delta of zero produces a factor of one", () => {
    expect(factorFromLevelDelta(10, 0, bounds)).toBe(1);
  });
});
