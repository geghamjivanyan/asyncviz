import { describe, expect, it } from "vitest";
import { TimelineZoomMetrics } from "@/dashboard/timeline/zoom/TimelineZoomMetrics";

describe("TimelineZoomMetrics", () => {
  it("counts zoom operations by kind", () => {
    const m = new TimelineZoomMetrics();
    m.recordZoomIn();
    m.recordZoomOut();
    m.recordZoomOut();
    m.recordZoomByFactor();
    const snap = m.snapshot();
    expect(snap.zoomIns).toBe(1);
    expect(snap.zoomOuts).toBe(2);
    expect(snap.zoomByFactor).toBe(1);
  });

  it("tracks fit kinds in a per-kind map", () => {
    const m = new TimelineZoomMetrics();
    m.recordZoomFit("fit-all");
    m.recordZoomFit("fit-all");
    m.recordZoomFit("fit-selection");
    const snap = m.snapshot();
    expect(snap.fitsByKind["fit-all"]).toBe(2);
    expect(snap.fitsByKind["fit-selection"]).toBe(1);
  });

  it("records constraint hits + noops separately", () => {
    const m = new TimelineZoomMetrics();
    m.recordConstraintHit("min");
    m.recordConstraintHit("max");
    m.recordNoopSuppressed();
    const snap = m.snapshot();
    expect(snap.constraintHitsMin).toBe(1);
    expect(snap.constraintHitsMax).toBe(1);
    expect(snap.noopsSuppressed).toBe(1);
  });

  it("records zoom latency stats", () => {
    const m = new TimelineZoomMetrics();
    m.recordZoomLatency(2);
    m.recordZoomLatency(5);
    m.recordZoomLatency(1);
    const snap = m.snapshot();
    expect(snap.totalZoomLatencyMs).toBe(8);
    expect(snap.maxZoomLatencyMs).toBe(5);
    expect(snap.lastZoomLatencyMs).toBe(1);
  });

  it("reset clears every counter", () => {
    const m = new TimelineZoomMetrics();
    m.recordZoomIn();
    m.recordZoomFit("fit-all");
    m.reset();
    const snap = m.snapshot();
    expect(snap.zoomIns).toBe(0);
    expect(snap.zoomFits).toBe(0);
  });
});
