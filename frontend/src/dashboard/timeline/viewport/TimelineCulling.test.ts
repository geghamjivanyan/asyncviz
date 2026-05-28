import { describe, expect, it } from "vitest";
import { cullRows, cullSegments } from "@/dashboard/timeline/viewport/TimelineCulling";
import { makeCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";

const camera = { timeStart: 0, timeEnd: 10, rowStart: 5, rowHeight: 20 };
const viewport = { cssWidth: 200, cssHeight: 80, devicePixelRatio: 1 };

describe("cullRows", () => {
  it("returns only rows in the visible range", () => {
    const coords = makeCoordinateSystem(camera, viewport);
    const rows = Array.from({ length: 50 }, (_, i) => ({ rowIndex: i, taskId: `t${i}` }));
    const out = cullRows(rows, coords);
    // 80/20 = 4 rows visible + 1 overscan = 5; starting at rowStart 5.
    expect(out.length).toBeLessThanOrEqual(5);
    out.forEach((row) => {
      expect(row.rowIndex).toBeGreaterThanOrEqual(5);
      expect(row.rowIndex).toBeLessThanOrEqual(9);
    });
  });
});

describe("cullSegments", () => {
  it("drops segments outside both axes", () => {
    const coords = makeCoordinateSystem(camera, viewport);
    const segments = [
      { rowIndex: 0, startSeconds: 0, endSeconds: 1 }, // row out
      { rowIndex: 6, startSeconds: 5, endSeconds: 6 }, // visible
      { rowIndex: 6, startSeconds: 100, endSeconds: 200 }, // time out
    ];
    const out = cullSegments(segments, coords, 50);
    expect(out).toHaveLength(1);
    expect(out[0]!.rowIndex).toBe(6);
  });
});
