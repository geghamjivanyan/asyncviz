import { describe, expect, it } from "vitest";
import { TimelineWindowMetrics } from "@/dashboard/timeline/virtualization/TimelineWindowMetrics";

describe("TimelineWindowMetrics", () => {
  it("tracks window resolutions + cache hit subset", () => {
    const metrics = new TimelineWindowMetrics();
    metrics.recordWindowResolution({ fromCache: false });
    metrics.recordWindowResolution({ fromCache: true });
    metrics.recordWindowResolution({ fromCache: true });
    const snap = metrics.snapshot();
    expect(snap.windowResolutions).toBe(3);
    expect(snap.windowCacheHits).toBe(2);
  });

  it("tracks row + segment culls", () => {
    const metrics = new TimelineWindowMetrics();
    metrics.recordRowCull({ visible: 5, total: 20 });
    metrics.recordSegmentCull({ visible: 30, total: 200 });
    const snap = metrics.snapshot();
    expect(snap.rowCulls).toBe(1);
    expect(snap.visibleRowsTotal).toBe(5);
    expect(snap.rowsCulledTotal).toBe(15);
    expect(snap.segmentCulls).toBe(1);
    expect(snap.visibleSegmentsTotal).toBe(30);
    expect(snap.segmentsCulledTotal).toBe(170);
  });

  it("flags recalculations over the 4ms budget", () => {
    const metrics = new TimelineWindowMetrics();
    metrics.recordRecalculation(2);
    metrics.recordRecalculation(10);
    expect(metrics.snapshot().recalculationsOverBudget).toBe(1);
    expect(metrics.snapshot().maxRecalculationMs).toBe(10);
  });

  it("reset clears every counter", () => {
    const metrics = new TimelineWindowMetrics();
    metrics.recordWindowResolution({ fromCache: false });
    metrics.recordRowCull({ visible: 1, total: 10 });
    metrics.reset();
    const snap = metrics.snapshot();
    expect(snap.windowResolutions).toBe(0);
    expect(snap.rowCulls).toBe(0);
  });
});
