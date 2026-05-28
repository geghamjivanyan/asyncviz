import { describe, expect, it } from "vitest";
import { TimelineRendererMetrics } from "@/dashboard/timeline/observability/timelineRendererMetrics";

describe("TimelineRendererMetrics", () => {
  it("starts at zero", () => {
    const m = new TimelineRendererMetrics();
    const snap = m.snapshot();
    expect(snap.framesRendered).toBe(0);
    expect(snap.maxFrameDurationMs).toBe(0);
    Object.values(snap.invalidationsByReason).forEach((v) => expect(v).toBe(0));
  });

  it("tracks frame durations + visible counts", () => {
    const m = new TimelineRendererMetrics();
    m.recordFrame({ durationMs: 2, visibleRowCount: 10, visibleSegmentCount: 50 });
    m.recordFrame({ durationMs: 5, visibleRowCount: 20, visibleSegmentCount: 100 });
    const snap = m.snapshot();
    expect(snap.framesRendered).toBe(2);
    expect(snap.lastFrameDurationMs).toBeCloseTo(5);
    expect(snap.maxFrameDurationMs).toBeCloseTo(5);
    expect(snap.visibleRowsTotal).toBe(30);
    expect(snap.visibleSegmentsTotal).toBe(150);
  });

  it("flags dropped frames above 16ms", () => {
    const m = new TimelineRendererMetrics();
    m.recordFrame({ durationMs: 17, visibleRowCount: 0, visibleSegmentCount: 0 });
    expect(m.snapshot().droppedFrameWarnings).toBe(1);
  });

  it("counts invalidations by reason", () => {
    const m = new TimelineRendererMetrics();
    m.recordInvalidation("camera");
    m.recordInvalidation("camera");
    m.recordInvalidation("data");
    const snap = m.snapshot();
    expect(snap.invalidationsByReason.camera).toBe(2);
    expect(snap.invalidationsByReason.data).toBe(1);
  });

  it("resets every counter", () => {
    const m = new TimelineRendererMetrics();
    m.recordFrame({ durationMs: 5, visibleRowCount: 1, visibleSegmentCount: 1 });
    m.recordInvalidation("manual");
    m.recordResize();
    m.reset();
    expect(m.snapshot().framesRendered).toBe(0);
    expect(m.snapshot().resizeEvents).toBe(0);
  });
});
