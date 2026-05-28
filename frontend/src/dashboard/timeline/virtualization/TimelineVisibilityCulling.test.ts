import { describe, expect, it } from "vitest";
import {
  cullRowsByWindow,
  cullSegmentsIndexed,
  cullSegmentsLinear,
} from "@/dashboard/timeline/virtualization/TimelineVisibilityCulling";
import { TimelineSegmentSpatialIndex } from "@/dashboard/timeline/virtualization/utils/spatialIndex";
import {
  makeFakeRows,
  makeFakeSegments,
} from "@/dashboard/timeline/virtualization/__fixtures__/makeFixtures";

const rowWindow = {
  startIndex: 5,
  endIndex: 10,
  overscanStartIndex: 4,
  overscanEndIndex: 12,
  totalRows: 100,
};
const timeWindow = {
  startSeconds: 2,
  endSeconds: 8,
  overscanStartSeconds: 1.5,
  overscanEndSeconds: 8.5,
};

describe("cullRowsByWindow", () => {
  it("slices rows by the overscan range", () => {
    const rows = makeFakeRows(20);
    const sliced = cullRowsByWindow(rows, rowWindow);
    expect(sliced.map((r) => r.rowIndex)).toEqual([4, 5, 6, 7, 8, 9, 10, 11]);
  });

  it("returns empty when the window is past the array end", () => {
    const rows = makeFakeRows(3);
    const sliced = cullRowsByWindow(rows, rowWindow);
    expect(sliced).toHaveLength(0);
  });
});

describe("cullSegmentsLinear", () => {
  it("filters segments by row + time window", () => {
    const segments = makeFakeSegments({ rowCount: 20, segmentsPerRow: 3 });
    const visible = cullSegmentsLinear({ segments, rowWindow, timeWindow });
    visible.forEach((s) => {
      expect(s.rowIndex).toBeGreaterThanOrEqual(rowWindow.overscanStartIndex);
      expect(s.rowIndex).toBeLessThan(rowWindow.overscanEndIndex);
      expect(s.endSeconds).toBeGreaterThanOrEqual(timeWindow.overscanStartSeconds);
      expect(s.startSeconds).toBeLessThanOrEqual(timeWindow.overscanEndSeconds);
    });
  });

  it("keeps active segments visible even when their wire end is in the past", () => {
    const segments = [
      {
        segmentId: "act",
        rowIndex: 5,
        taskId: "t5",
        startSeconds: 0,
        endSeconds: 0,
        isActive: true,
      },
    ];
    const visible = cullSegmentsLinear({ segments, rowWindow, timeWindow });
    expect(visible).toHaveLength(1);
  });
});

describe("cullSegmentsIndexed", () => {
  it("produces the same result as the linear cull", () => {
    const segments = makeFakeSegments({ rowCount: 50, segmentsPerRow: 10 });
    const index = new TimelineSegmentSpatialIndex(segments);
    const linear = cullSegmentsLinear({ segments, rowWindow, timeWindow });
    const indexed = cullSegmentsIndexed({ index, rowWindow, timeWindow });
    const linearIds = linear.map((s) => s.segmentId).sort();
    const indexedIds = indexed.map((s) => s.segmentId).sort();
    expect(indexedIds).toEqual(linearIds);
  });
});
