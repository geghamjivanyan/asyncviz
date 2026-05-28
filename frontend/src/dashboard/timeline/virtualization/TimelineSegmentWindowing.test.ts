import { describe, expect, it } from "vitest";
import { TimelineSegmentWindowing } from "@/dashboard/timeline/virtualization/TimelineSegmentWindowing";
import { makeFakeSegments } from "@/dashboard/timeline/virtualization/__fixtures__/makeFixtures";

const rowWindow = {
  startIndex: 0,
  endIndex: 10,
  overscanStartIndex: 0,
  overscanEndIndex: 10,
  totalRows: 100,
};
const timeWindow = {
  startSeconds: 0,
  endSeconds: 5,
  overscanStartSeconds: -1,
  overscanEndSeconds: 6,
};

describe("TimelineSegmentWindowing", () => {
  it("falls back to linear culling below the indexed threshold", () => {
    const windowing = new TimelineSegmentWindowing({ indexMinSegments: 1024 });
    const segments = makeFakeSegments({ rowCount: 10, segmentsPerRow: 4 });
    const result = windowing.resolve({ segments, sequence: 1, rowWindow, timeWindow });
    result.forEach((s) => {
      expect(s.rowIndex).toBeLessThan(10);
    });
  });

  it("builds the spatial index above the indexed threshold", () => {
    const windowing = new TimelineSegmentWindowing({ indexMinSegments: 4 });
    const segments = makeFakeSegments({ rowCount: 4, segmentsPerRow: 5 });
    windowing.resolve({ segments, sequence: 1, rowWindow, timeWindow });
    expect(windowing.metrics().indexBuilds).toBe(1);
    expect(windowing.metrics().indexed).toBe(true);
  });

  it("rebuilds the index when the sequence advances", () => {
    const windowing = new TimelineSegmentWindowing({ indexMinSegments: 4 });
    const segments = makeFakeSegments({ rowCount: 4, segmentsPerRow: 5 });
    windowing.resolve({ segments, sequence: 1, rowWindow, timeWindow });
    windowing.resolve({ segments, sequence: 2, rowWindow, timeWindow });
    expect(windowing.metrics().indexBuilds).toBe(2);
  });

  it("reuses the index when sequence + length match", () => {
    const windowing = new TimelineSegmentWindowing({ indexMinSegments: 4 });
    const segments = makeFakeSegments({ rowCount: 4, segmentsPerRow: 5 });
    windowing.resolve({ segments, sequence: 1, rowWindow, timeWindow });
    windowing.resolve({ segments, sequence: 1, rowWindow, timeWindow });
    expect(windowing.metrics().indexBuilds).toBe(1);
  });

  it("invalidate clears the index", () => {
    const windowing = new TimelineSegmentWindowing({ indexMinSegments: 4 });
    const segments = makeFakeSegments({ rowCount: 4, segmentsPerRow: 5 });
    windowing.resolve({ segments, sequence: 1, rowWindow, timeWindow });
    windowing.invalidate();
    expect(windowing.metrics().indexed).toBe(false);
  });
});
