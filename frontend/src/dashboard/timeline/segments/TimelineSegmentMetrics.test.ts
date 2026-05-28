import { describe, expect, it } from "vitest";
import { TimelineSegmentMetrics } from "@/dashboard/timeline/segments/TimelineSegmentMetrics";

describe("TimelineSegmentMetrics", () => {
  it("records segments + frames", () => {
    const metrics = new TimelineSegmentMetrics();
    metrics.recordSegment();
    metrics.recordSegment();
    metrics.recordFrame({
      durationMs: 3,
      visibleSegments: 2,
      culled: 1,
      overlaps: 0,
      replayMarked: false,
      activeSegments: 0,
    });
    const snap = metrics.snapshot();
    expect(snap.segmentsRendered).toBe(2);
    expect(snap.visibleSegmentsTotal).toBe(2);
    expect(snap.segmentsCulled).toBe(1);
    expect(snap.lastFrameMs).toBe(3);
  });

  it("flags long frames as dropped", () => {
    const metrics = new TimelineSegmentMetrics();
    metrics.recordFrame({
      durationMs: 50,
      visibleSegments: 1,
      culled: 0,
      overlaps: 0,
      replayMarked: false,
      activeSegments: 0,
    });
    expect(metrics.snapshot().droppedFrameWarnings).toBe(1);
  });

  it("tallies geometry cache hits + misses + evictions", () => {
    const metrics = new TimelineSegmentMetrics();
    metrics.recordGeometry({ hits: 4, misses: 2, evictions: 1 });
    const snap = metrics.snapshot();
    expect(snap.geometryCacheHits).toBe(4);
    expect(snap.geometryCacheMisses).toBe(2);
    expect(snap.geometryCacheEvictions).toBe(1);
    expect(snap.geometryComputations).toBe(2);
  });

  it("tracks projection durations", () => {
    const metrics = new TimelineSegmentMetrics();
    metrics.recordProjection(2);
    metrics.recordProjection(7);
    const snap = metrics.snapshot();
    expect(snap.projectionsBuilt).toBe(2);
    expect(snap.projectionTotalMs).toBe(9);
    expect(snap.projectionMaxMs).toBe(7);
  });

  it("reset clears counters", () => {
    const metrics = new TimelineSegmentMetrics();
    metrics.recordSegment();
    metrics.recordFrame({
      durationMs: 5,
      visibleSegments: 1,
      culled: 0,
      overlaps: 0,
      replayMarked: true,
      activeSegments: 1,
    });
    metrics.reset();
    expect(metrics.snapshot().segmentsRendered).toBe(0);
    expect(metrics.snapshot().replayMarkedFrames).toBe(0);
  });
});
