import { describe, expect, it } from "vitest";
import { hitTestRow, rowBoundingBox } from "@/dashboard/timeline/rows/TimelineRowHitTesting";
import { normalizeRow } from "@/dashboard/timeline/rows/utils/normalizeRow";
import { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import { makeRowLayout } from "@/dashboard/timeline/rows/TimelineRowLayout";

function setup() {
  const coords = new TimelineCoordinateSystem(
    { timeStart: 0, timeEnd: 10, rowStart: 0, rowHeight: 22 },
    { cssWidth: 800, cssHeight: 220, devicePixelRatio: 1 },
  );
  const layout = makeRowLayout({ labelColumnWidthPx: 150, columnGutterPx: 6 }).resolve(coords);
  const rows = [
    normalizeRow({ rowIndex: 0, taskId: "a", label: "A", state: "running" }),
    normalizeRow({ rowIndex: 1, taskId: "b", label: "B", state: "waiting" }),
  ];
  return { coords, layout, rows };
}

describe("hitTestRow", () => {
  it("locates the row under the pointer in the timeline column", () => {
    const { coords, layout, rows } = setup();
    const result = hitTestRow({ xCss: 500, yCss: 28, coords, layout, rows });
    expect(result.row?.taskId).toBe("b");
    expect(result.zone).toBe("timeline");
    expect(result.timeSeconds).not.toBeNull();
  });

  it("identifies clicks in the label column", () => {
    const { coords, layout, rows } = setup();
    const result = hitTestRow({ xCss: 50, yCss: 5, coords, layout, rows });
    expect(result.row?.taskId).toBe("a");
    expect(result.zone).toBe("label");
    expect(result.timeSeconds).toBeNull();
  });

  it("returns null row when the pointer is below the dataset", () => {
    const { coords, layout, rows } = setup();
    const result = hitTestRow({ xCss: 200, yCss: 200, coords, layout, rows });
    expect(result.row).toBeNull();
    expect(result.zone).toBeNull();
  });

  it("computes deterministic row bounding boxes", () => {
    const { coords, layout } = setup();
    expect(rowBoundingBox({ rowIndex: 0, coords, layout })).toEqual({
      x: 0,
      y: 0,
      width: 800,
      height: 22,
    });
    expect(rowBoundingBox({ rowIndex: 2, coords, layout })).toEqual({
      x: 0,
      y: 44,
      width: 800,
      height: 22,
    });
  });
});
