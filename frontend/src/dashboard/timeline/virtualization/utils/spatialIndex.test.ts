import { describe, expect, it } from "vitest";
import { TimelineSegmentSpatialIndex } from "@/dashboard/timeline/virtualization/utils/spatialIndex";
import { makeFakeSegments } from "@/dashboard/timeline/virtualization/__fixtures__/makeFixtures";

describe("TimelineSegmentSpatialIndex", () => {
  it("returns empty results for an empty dataset", () => {
    const index = new TimelineSegmentSpatialIndex([]);
    expect(
      index.query({ startRowIndex: 0, endRowIndex: 10, startSeconds: 0, endSeconds: 5 }),
    ).toEqual([]);
  });

  it("returns segments whose row + time intersects the query window", () => {
    const segments = makeFakeSegments({ rowCount: 10, segmentsPerRow: 5 });
    const index = new TimelineSegmentSpatialIndex(segments);
    const result = index.query({
      startRowIndex: 2,
      endRowIndex: 4,
      startSeconds: 1,
      endSeconds: 3,
    });
    result.forEach((s) => {
      expect(s.rowIndex).toBeGreaterThanOrEqual(2);
      expect(s.rowIndex).toBeLessThan(4);
    });
    expect(result.length).toBeGreaterThan(0);
  });

  it("keeps active segments visible past their wire end", () => {
    const index = new TimelineSegmentSpatialIndex([
      {
        segmentId: "active",
        rowIndex: 0,
        startSeconds: 0,
        endSeconds: 0,
        isActive: true,
      },
    ]);
    const result = index.query({
      startRowIndex: 0,
      endRowIndex: 1,
      startSeconds: 5,
      endSeconds: 10,
      cameraEndSeconds: 10,
    });
    expect(result).toHaveLength(1);
  });

  it("is faster than O(N) for large datasets — sanity check", () => {
    const segments = makeFakeSegments({ rowCount: 200, segmentsPerRow: 100 });
    const index = new TimelineSegmentSpatialIndex(segments);
    const result = index.query({
      startRowIndex: 50,
      endRowIndex: 55,
      startSeconds: 30,
      endSeconds: 40,
    });
    expect(result.length).toBeGreaterThan(0);
    // Spatial queries should keep lookups proportional to result size,
    // not total size.
    expect(index.metrics().lookups).toBeLessThan(segments.length);
  });
});
