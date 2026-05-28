import { describe, expect, it } from "vitest";
import {
  TimelineTimeScale,
  safeScale,
} from "@/dashboard/timeline/scaling/TimelineTimeScale";

describe("TimelineTimeScale", () => {
  it("pre-computes pixelsPerSecond + secondsPerPixel", () => {
    const scale = new TimelineTimeScale(0, 10, 800);
    expect(scale.pixelsPerSecond).toBeCloseTo(80);
    expect(scale.secondsPerPixel).toBeCloseTo(1 / 80);
    expect(scale.durationSeconds).toBe(10);
  });

  it("timeToX + xToTime are exact inverses", () => {
    const scale = new TimelineTimeScale(5, 15, 1000);
    for (const x of [0, 250, 500, 750, 1000]) {
      expect(scale.timeToX(scale.xToTime(x))).toBeCloseTo(x, 6);
    }
    for (const t of [5, 7.5, 10, 12.5, 15]) {
      expect(scale.xToTime(scale.timeToX(t))).toBeCloseTo(t, 6);
    }
  });

  it("intersectsTime correctly detects overlap", () => {
    const scale = new TimelineTimeScale(0, 10, 100);
    expect(scale.intersectsTime(-1, 0)).toBe(true);
    expect(scale.intersectsTime(10, 12)).toBe(true);
    expect(scale.intersectsTime(-5, -1)).toBe(false);
    expect(scale.intersectsTime(11, 12)).toBe(false);
  });

  it("projectRange returns clipped spans for partially-visible segments", () => {
    const scale = new TimelineTimeScale(0, 10, 100);
    const partial = scale.projectRange(-2, 5);
    expect(partial).not.toBeNull();
    expect(partial!.x0).toBe(0);
    expect(partial!.clippedLeft).toBe(true);
    const fully = scale.projectRange(2, 4);
    expect(fully!.clippedLeft).toBe(false);
    expect(fully!.clippedRight).toBe(false);
    expect(scale.projectRange(100, 200)).toBeNull();
  });

  it("rejects non-finite or non-positive inputs", () => {
    expect(() => new TimelineTimeScale(NaN, 10, 100)).toThrow();
    expect(() => new TimelineTimeScale(0, 10, 0)).toThrow();
    expect(() => new TimelineTimeScale(0, 10, -1)).toThrow();
  });

  it("safeScale falls back to a defensive minimum width + duration", () => {
    const scale = safeScale(0, 0, 0);
    expect(scale.widthPx).toBeGreaterThan(0);
    expect(scale.durationSeconds).toBeGreaterThan(0);
  });

  it("isNumericallySafe returns false for absurd inputs", () => {
    const wild = safeScale(1e16, 1e16 + 1, 1);
    expect(wild.isNumericallySafe()).toBe(false);
  });
});
