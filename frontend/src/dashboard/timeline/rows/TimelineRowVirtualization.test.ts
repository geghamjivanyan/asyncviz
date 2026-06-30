import { describe, expect, it } from "vitest";
import {
  resolveVisibleRows,
  virtualContentHeight,
} from "@/dashboard/timeline/rows/TimelineRowVirtualization";
import { normalizeRow } from "@/dashboard/timeline/rows/utils/normalizeRow";
import { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";

function buildRows(count: number) {
  const rows = [];
  for (let i = 0; i < count; i += 1) {
    rows.push(normalizeRow({ rowIndex: i, taskId: `t${i}`, label: `Row ${i}`, state: "running" }));
  }
  return rows;
}

function buildCoords({
  rowStart,
  cssHeight,
  rowHeight,
}: {
  rowStart: number;
  cssHeight: number;
  rowHeight: number;
}) {
  return new TimelineCoordinateSystem(
    { timeStart: 0, timeEnd: 10, rowStart, rowHeight },
    { cssWidth: 600, cssHeight, devicePixelRatio: 1 },
  );
}

describe("resolveVisibleRows", () => {
  it("returns the empty result when there are no rows", () => {
    const coords = buildCoords({ rowStart: 0, cssHeight: 100, rowHeight: 20 });
    expect(resolveVisibleRows([], coords).rows).toEqual([]);
  });

  it("only returns rows inside the visible window by default", () => {
    const rows = buildRows(100);
    const coords = buildCoords({ rowStart: 10, cssHeight: 60, rowHeight: 20 });
    const result = resolveVisibleRows(rows, coords);
    expect(result.rows.map((r) => r.rowIndex)).toEqual([10, 11, 12, 13]);
  });

  it("respects overscan padding", () => {
    const rows = buildRows(100);
    const coords = buildCoords({ rowStart: 10, cssHeight: 60, rowHeight: 20 });
    const result = resolveVisibleRows(rows, coords, { overscan: 2 });
    expect(result.startIndex).toBe(8);
    // ceil(60/20)+1 visible rows = 4, plus 2 overscan on each side.
    expect(result.endIndex).toBe(16);
  });

  it("clamps overscan at the array edges", () => {
    const rows = buildRows(5);
    const coords = buildCoords({ rowStart: 0, cssHeight: 200, rowHeight: 20 });
    const result = resolveVisibleRows(rows, coords, { overscan: 10 });
    expect(result.startIndex).toBe(0);
    expect(result.endIndex).toBe(5);
  });

  it("computes deterministic content height", () => {
    expect(virtualContentHeight(0, 20)).toBe(0);
    expect(virtualContentHeight(10, 20)).toBe(200);
    expect(virtualContentHeight(5, 0)).toBe(0);
  });
});
