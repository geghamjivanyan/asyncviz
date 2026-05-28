import { describe, expect, it } from "vitest";
import { makeRowLayout } from "@/dashboard/timeline/rows/TimelineRowLayout";
import { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";

function coords(width: number) {
  return new TimelineCoordinateSystem(
    { timeStart: 0, timeEnd: 10, rowStart: 0, rowHeight: 22 },
    { cssWidth: width, cssHeight: 200, devicePixelRatio: 1 },
  );
}

describe("TimelineRowLayout", () => {
  it("clamps the label column to the configured min when the viewport is narrow", () => {
    const layout = makeRowLayout({
      labelColumnWidthPx: 400,
      minLabelColumnWidthPx: 80,
      maxLabelColumnWidthPx: 200,
    });
    const snapshot = layout.resolve(coords(120));
    expect(snapshot.labelColumnWidthPx).toBeGreaterThanOrEqual(80);
    expect(snapshot.labelColumnWidthPx).toBeLessThanOrEqual(200);
    expect(snapshot.timelineColumnX).toBe(
      snapshot.labelColumnWidthPx + snapshot.columnGutterPx,
    );
  });

  it("places the timeline column right of the label column", () => {
    const layout = makeRowLayout({
      labelColumnWidthPx: 150,
      minLabelColumnWidthPx: 96,
      maxLabelColumnWidthPx: 220,
      columnGutterPx: 6,
    });
    const snapshot = layout.resolve(coords(800));
    expect(snapshot.timelineColumnX).toBe(snapshot.labelColumnWidthPx + 6);
    expect(snapshot.timelineColumnWidthPx).toBe(800 - snapshot.timelineColumnX);
  });

  it("caps lineage indentation at maxIndentPx", () => {
    const layout = makeRowLayout({ indentPerDepthPx: 12, maxIndentPx: 36 });
    expect(layout.indentForDepth(0)).toBe(0);
    expect(layout.indentForDepth(1)).toBe(12);
    expect(layout.indentForDepth(3)).toBe(36);
    expect(layout.indentForDepth(20)).toBe(36);
  });

  it("computes deterministic row Y coordinates", () => {
    const layout = makeRowLayout({ rowHeightPx: 24 });
    expect(layout.rowTopY(0, 0)).toBe(0);
    expect(layout.rowTopY(3, 0)).toBe(72);
    expect(layout.rowCenterY(2, 0)).toBe(60);
  });

  it("snapshot is replay-stable for identical viewports", () => {
    const layout = makeRowLayout();
    const a = layout.resolve(coords(640));
    const b = layout.resolve(coords(640));
    expect(a).toEqual(b);
  });
});
