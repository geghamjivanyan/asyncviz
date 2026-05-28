import { describe, expect, it } from "vitest";
import { EventFeedMetrics } from "@/dashboard/events/observability/feedMetrics";

describe("EventFeedMetrics", () => {
  it("starts at zero", () => {
    const metrics = new EventFeedMetrics();
    const snap = metrics.snapshot();
    expect(snap.projectionRebuilds).toBe(0);
    expect(snap.pipelineRuns).toBe(0);
    expect(snap.rowRenders).toBe(0);
    expect(snap.groupRebuilds).toBe(0);
  });

  it("records projections + tracks max", () => {
    const metrics = new EventFeedMetrics();
    metrics.recordProjection(5, 1.0);
    metrics.recordProjection(8, 3.2);
    metrics.recordProjection(2, 2.0);
    expect(metrics.snapshot().projectionRebuilds).toBe(3);
    expect(metrics.snapshot().rowsProjectedTotal).toBe(15);
    expect(metrics.snapshot().maxProjectionMs).toBeCloseTo(3.2);
  });

  it("ignores invalid durations", () => {
    const metrics = new EventFeedMetrics();
    metrics.recordPipeline(Number.NaN);
    metrics.recordPipeline(-1);
    expect(metrics.snapshot().maxPipelineMs).toBe(0);
  });

  it("tracks live + replay appends", () => {
    const metrics = new EventFeedMetrics();
    metrics.recordLiveAppend();
    metrics.recordLiveAppend(3);
    metrics.recordReplayAppend(5);
    expect(metrics.snapshot().liveAppends).toBe(4);
    expect(metrics.snapshot().replayAppends).toBe(5);
  });

  it("resets every counter", () => {
    const metrics = new EventFeedMetrics();
    metrics.recordPipeline(1);
    metrics.recordProjection(2, 2);
    metrics.recordLiveAppend();
    metrics.reset();
    const snap = metrics.snapshot();
    expect(snap.projectionRebuilds).toBe(0);
    expect(snap.pipelineRuns).toBe(0);
    expect(snap.liveAppends).toBe(0);
  });
});
