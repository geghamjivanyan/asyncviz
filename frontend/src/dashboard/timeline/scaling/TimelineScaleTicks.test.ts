import { describe, expect, it } from "vitest";
import { TimelineTimeScale } from "@/dashboard/timeline/scaling/TimelineTimeScale";
import { generateTicks } from "@/dashboard/timeline/scaling/TimelineScaleTicks";
import { gridFromTicks } from "@/dashboard/timeline/scaling/TimelineScaleGrid";

describe("generateTicks", () => {
  it("produces ticks across the visible window", () => {
    const scale = new TimelineTimeScale(0, 10, 800);
    const list = generateTicks(scale, { targetMajorSpacingPx: 80, minorRatio: 5 });
    expect(list.ticks.length).toBeGreaterThan(0);
    list.ticks.forEach((tick) => {
      expect(tick.timeSeconds).toBeGreaterThanOrEqual(-list.minorIntervalSeconds);
      expect(tick.timeSeconds).toBeLessThanOrEqual(scale.timeEnd + 1e-6);
    });
  });

  it("emits major + minor ticks at the configured ratio", () => {
    const scale = new TimelineTimeScale(0, 5, 500);
    const list = generateTicks(scale, { targetMajorSpacingPx: 100, minorRatio: 5 });
    const majors = list.ticks.filter((t) => t.major);
    const minors = list.ticks.filter((t) => !t.major);
    expect(majors.length).toBeGreaterThan(0);
    expect(minors.length).toBeGreaterThanOrEqual(majors.length);
  });

  it("labels only major ticks", () => {
    const scale = new TimelineTimeScale(0, 10, 800);
    const list = generateTicks(scale);
    for (const tick of list.ticks) {
      if (tick.major) expect(tick.label).not.toBeNull();
      else expect(tick.label).toBeNull();
    }
  });

  it("caps the tick count to maxTicks", () => {
    const scale = new TimelineTimeScale(0, 10, 800);
    const list = generateTicks(scale, { maxTicks: 16 });
    expect(list.ticks.length).toBeLessThanOrEqual(16);
  });

  it("is deterministic for the same scale", () => {
    const scale = new TimelineTimeScale(0, 10, 800);
    const a = generateTicks(scale);
    const b = generateTicks(scale);
    expect(a.ticks).toEqual(b.ticks);
    expect(a.majorIntervalSeconds).toBe(b.majorIntervalSeconds);
  });
});

describe("gridFromTicks", () => {
  it("splits ticks into major/minor x arrays", () => {
    const scale = new TimelineTimeScale(0, 10, 800);
    const list = generateTicks(scale);
    const grid = gridFromTicks(list);
    expect(grid.majorXs.length + grid.minorXs.length).toBe(list.ticks.length);
  });
});
