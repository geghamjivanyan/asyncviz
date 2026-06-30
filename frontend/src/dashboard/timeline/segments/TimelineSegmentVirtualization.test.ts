import { describe, expect, it } from "vitest";
import {
  resolveVisibleSegments,
  segmentsOverlap,
} from "@/dashboard/timeline/segments/TimelineSegmentVirtualization";
import { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import { makeProjectionEntry } from "@/dashboard/timeline/segments/__fixtures__/makeSegment";

function buildCoords({
  rowStart = 0,
  cssHeight = 200,
  rowHeight = 20,
  timeStart = 0,
  timeEnd = 10,
}: {
  rowStart?: number;
  cssHeight?: number;
  rowHeight?: number;
  timeStart?: number;
  timeEnd?: number;
} = {}) {
  return new TimelineCoordinateSystem(
    { timeStart, timeEnd, rowStart, rowHeight },
    { cssWidth: 600, cssHeight, devicePixelRatio: 1 },
  );
}

describe("resolveVisibleSegments", () => {
  it("returns the empty result when there are no entries", () => {
    const coords = buildCoords();
    expect(resolveVisibleSegments([], coords, 0).entries).toEqual([]);
  });

  it("culls entries outside the visible row range", () => {
    const coords = buildCoords({ rowStart: 10, cssHeight: 60 });
    const entries = [
      makeProjectionEntry("a", 0, 1, 2),
      makeProjectionEntry("b", 11, 1, 2),
      makeProjectionEntry("c", 12, 3, 4),
    ];
    const result = resolveVisibleSegments(entries, coords, 100);
    expect(result.entries.map((e) => e.segmentId)).toEqual(["b", "c"]);
  });

  it("culls entries outside the visible time window", () => {
    const coords = buildCoords({ timeStart: 5, timeEnd: 10 });
    const entries = [
      makeProjectionEntry("early", 0, 0, 1),
      makeProjectionEntry("late", 0, 12, 14),
      makeProjectionEntry("ok", 0, 6, 7),
    ];
    const result = resolveVisibleSegments(entries, coords, 50);
    expect(result.entries.map((e) => e.segmentId)).toEqual(["ok"]);
  });

  it("keeps active segments visible even when their end is in the past", () => {
    const coords = buildCoords({ timeStart: 5, timeEnd: 10 });
    const entries = [makeProjectionEntry("active", 0, 4, 4, { isActive: true })];
    const result = resolveVisibleSegments(entries, coords, 50);
    expect(result.entries).toHaveLength(1);
  });

  it("respects overscan padding on rows and time", () => {
    const coords = buildCoords({ rowStart: 10, cssHeight: 60, timeStart: 5, timeEnd: 6 });
    const entries = [makeProjectionEntry("borderline", 9, 4.5, 4.9)];
    const result = resolveVisibleSegments(entries, coords, 50, {
      rowOverscan: 2,
      timeOverscanSeconds: 1,
    });
    expect(result.entries).toHaveLength(1);
  });
});

describe("segmentsOverlap", () => {
  it("detects overlap on the same row", () => {
    const a = makeProjectionEntry("a", 0, 1, 5);
    const b = makeProjectionEntry("b", 0, 4, 6);
    expect(segmentsOverlap(a, b)).toBe(true);
  });

  it("ignores overlap on different rows", () => {
    const a = makeProjectionEntry("a", 0, 1, 5);
    const b = makeProjectionEntry("b", 1, 4, 6);
    expect(segmentsOverlap(a, b)).toBe(false);
  });

  it("treats touching ends as non-overlapping", () => {
    const a = makeProjectionEntry("a", 0, 1, 5);
    const b = makeProjectionEntry("b", 0, 5, 7);
    expect(segmentsOverlap(a, b)).toBe(false);
  });
});
