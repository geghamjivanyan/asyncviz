import { describe, expect, it } from "vitest";
import { TimelineScaleMetrics } from "@/dashboard/timeline/scaling/TimelineScaleMetrics";

describe("TimelineScaleMetrics", () => {
  it("counts scale changes by kind", () => {
    const m = new TimelineScaleMetrics();
    m.recordScaleChange("set");
    m.recordScaleChange("zoom");
    m.recordScaleChange("pan");
    m.recordScaleChange("fit");
    const s = m.snapshot();
    expect(s.scaleChanges).toBe(4);
    expect(s.scaleZooms).toBe(1);
    expect(s.scalePans).toBe(1);
    expect(s.scaleFits).toBe(1);
  });

  it("records tick generation timings + cache hits", () => {
    const m = new TimelineScaleMetrics();
    m.recordTickGeneration(1.5, false);
    m.recordTickGeneration(0, true);
    const s = m.snapshot();
    expect(s.ticksGenerated).toBe(1);
    expect(s.ticksFromCache).toBe(1);
    expect(s.cacheHits).toBe(1);
    expect(s.cacheMisses).toBe(1);
    expect(s.lastTickGenMs).toBe(1.5);
  });

  it("counts constraint hits + precision warnings", () => {
    const m = new TimelineScaleMetrics();
    m.recordConstraintHit("min");
    m.recordConstraintHit("min");
    m.recordConstraintHit("max");
    m.recordViewportNormalization(0.2, true);
    const s = m.snapshot();
    expect(s.constraintHitsMin).toBe(2);
    expect(s.constraintHitsMax).toBe(1);
    expect(s.precisionWarnings).toBe(1);
  });

  it("reset clears every counter", () => {
    const m = new TimelineScaleMetrics();
    m.recordScaleChange("zoom");
    m.recordTickGeneration(1, false);
    m.reset();
    const s = m.snapshot();
    expect(s.scaleChanges).toBe(0);
    expect(s.cacheMisses).toBe(0);
  });
});
