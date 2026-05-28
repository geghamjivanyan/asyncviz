import { describe, expect, it } from "vitest";
import { TimelineVirtualizationEngine } from "@/dashboard/timeline/virtualization/TimelineVirtualizationEngine";
import { TimelineWindowMetrics } from "@/dashboard/timeline/virtualization/TimelineWindowMetrics";
import {
  buildCoords,
  makeFakeRows,
  makeFakeSegments,
  type FakeRow,
  type FakeSegment,
} from "@/dashboard/timeline/virtualization/__fixtures__/makeFixtures";

describe("TimelineVirtualizationEngine", () => {
  it("returns a culled frame on first call + caches it on the second", () => {
    const metrics = new TimelineWindowMetrics();
    const engine = new TimelineVirtualizationEngine<FakeRow, FakeSegment>({ metrics });
    const coords = buildCoords({});
    const inputs = {
      rows: makeFakeRows(100),
      segments: makeFakeSegments({ rowCount: 100, segmentsPerRow: 4 }),
      sequence: 1,
    };
    const a = engine.resolveFrame({ coords, inputs });
    const b = engine.resolveFrame({ coords, inputs });
    expect(a).toBe(b);
    const snap = metrics.snapshot();
    expect(snap.cacheHits).toBe(1);
    expect(snap.cacheMisses).toBe(1);
  });

  it("invalidates the cache when the sequence advances", () => {
    const engine = new TimelineVirtualizationEngine<FakeRow, FakeSegment>();
    const coords = buildCoords({});
    const rows = makeFakeRows(20);
    const segments = makeFakeSegments({ rowCount: 20, segmentsPerRow: 2 });
    const a = engine.resolveFrame({ coords, inputs: { rows, segments, sequence: 1 } });
    const b = engine.resolveFrame({ coords, inputs: { rows, segments, sequence: 2 } });
    expect(a).not.toBe(b);
  });

  it("culls rows + segments to the visible window", () => {
    const metrics = new TimelineWindowMetrics();
    const engine = new TimelineVirtualizationEngine<FakeRow, FakeSegment>({
      metrics,
      overscan: { rowOverscan: 0, timeOverscanSeconds: 0 },
    });
    const coords = buildCoords({ rowStart: 10, cssHeight: 60, rowHeight: 20 });
    const rows = makeFakeRows(100);
    const segments = makeFakeSegments({ rowCount: 100, segmentsPerRow: 4 });
    const frame = engine.resolveFrame({ coords, inputs: { rows, segments, sequence: 1 } });
    expect(frame.rows.length).toBeLessThan(rows.length);
    expect(frame.segments.length).toBeLessThan(segments.length);
    const snap = metrics.snapshot();
    expect(snap.rowsCulledTotal).toBeGreaterThan(0);
    expect(snap.segmentsCulledTotal).toBeGreaterThan(0);
  });

  it("setOverscan invalidates the cache", () => {
    const engine = new TimelineVirtualizationEngine<FakeRow, FakeSegment>({
      overscan: { rowOverscan: 1 },
    });
    const coords = buildCoords({});
    const rows = makeFakeRows(20);
    const segments = makeFakeSegments({ rowCount: 20, segmentsPerRow: 2 });
    const a = engine.resolveFrame({ coords, inputs: { rows, segments, sequence: 1 } });
    engine.setOverscan({ rowOverscan: 8 });
    const b = engine.resolveFrame({ coords, inputs: { rows, segments, sequence: 1 } });
    expect(a).not.toBe(b);
  });

  it("invalidate forces a full re-cull", () => {
    const metrics = new TimelineWindowMetrics();
    const engine = new TimelineVirtualizationEngine<FakeRow, FakeSegment>({ metrics });
    const coords = buildCoords({});
    const rows = makeFakeRows(10);
    const segments = makeFakeSegments({ rowCount: 10, segmentsPerRow: 2 });
    engine.resolveFrame({ coords, inputs: { rows, segments, sequence: 1 } });
    engine.invalidate();
    engine.resolveFrame({ coords, inputs: { rows, segments, sequence: 1 } });
    expect(metrics.snapshot().cacheMisses).toBe(2);
    expect(metrics.snapshot().invalidationsObserved).toBe(1);
  });

  it("uses the spatial index for dense segment datasets", () => {
    const engine = new TimelineVirtualizationEngine<FakeRow, FakeSegment>({
      indexMinSegments: 4,
    });
    const coords = buildCoords({});
    const rows = makeFakeRows(50);
    const segments = makeFakeSegments({ rowCount: 50, segmentsPerRow: 20 });
    engine.resolveFrame({ coords, inputs: { rows, segments, sequence: 1 } });
    expect(engine.segmentMetrics().indexed).toBe(true);
  });

  it("emits a current window snapshot consumers can read", () => {
    const engine = new TimelineVirtualizationEngine<FakeRow, FakeSegment>();
    const coords = buildCoords({});
    engine.resolveFrame({
      coords,
      inputs: {
        rows: makeFakeRows(10),
        segments: makeFakeSegments({ rowCount: 10, segmentsPerRow: 2 }),
        sequence: 1,
      },
    });
    const window = engine.currentWindow();
    expect(window).not.toBeNull();
    expect(window!.rows.totalRows).toBe(10);
  });
});
