import { describe, expect, it } from "vitest";
import { TimelineRowMetrics } from "@/dashboard/timeline/rows/TimelineRowMetrics";

describe("TimelineRowMetrics", () => {
  it("records rows + frames into the snapshot", () => {
    const metrics = new TimelineRowMetrics();
    metrics.recordRow();
    metrics.recordRow();
    metrics.recordFrame({ durationMs: 4, visibleRows: 2, replayMarked: false });
    const snap = metrics.snapshot();
    expect(snap.rowsRendered).toBe(2);
    expect(snap.visibleRowsTotal).toBe(2);
    expect(snap.lastFrameMs).toBe(4);
    expect(snap.maxFrameMs).toBe(4);
  });

  it("flags frames over the 16ms budget as dropped", () => {
    const metrics = new TimelineRowMetrics();
    metrics.recordFrame({ durationMs: 20, visibleRows: 5, replayMarked: false });
    expect(metrics.snapshot().droppedFrameWarnings).toBe(1);
  });

  it("counts label truncations through recordLabel", () => {
    const metrics = new TimelineRowMetrics();
    metrics.recordLabel({ truncated: true });
    metrics.recordLabel({ truncated: false });
    const snap = metrics.snapshot();
    expect(snap.labelsRendered).toBe(2);
    expect(snap.labelsTruncated).toBe(1);
  });

  it("tracks projection build counts + max duration", () => {
    const metrics = new TimelineRowMetrics();
    metrics.recordProjection(1);
    metrics.recordProjection(7);
    metrics.recordProjection(3);
    const snap = metrics.snapshot();
    expect(snap.projectionsBuilt).toBe(3);
    expect(snap.projectionMaxMs).toBe(7);
    expect(snap.projectionTotalMs).toBe(11);
  });

  it("reset clears all counters", () => {
    const metrics = new TimelineRowMetrics();
    metrics.recordRow();
    metrics.recordFrame({ durationMs: 5, visibleRows: 1, replayMarked: true });
    metrics.reset();
    const snap = metrics.snapshot();
    expect(snap.rowsRendered).toBe(0);
    expect(snap.replayMarkedFrames).toBe(0);
  });
});
