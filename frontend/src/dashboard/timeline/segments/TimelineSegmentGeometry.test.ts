import { describe, expect, it } from "vitest";
import {
  crispStrokeRect,
  projectSegmentRect,
} from "@/dashboard/timeline/segments/TimelineSegmentGeometry";
import { makeSegmentLayout } from "@/dashboard/timeline/segments/TimelineSegmentLayout";
import { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import { makeProjectionEntry } from "@/dashboard/timeline/segments/__fixtures__/makeSegment";

function setup({
  columnX = 200,
  columnWidth = 600,
  rowHeight = 22,
}: { columnX?: number; columnWidth?: number; rowHeight?: number } = {}) {
  const coords = new TimelineCoordinateSystem(
    { timeStart: 0, timeEnd: 10, rowStart: 0, rowHeight },
    { cssWidth: columnX + columnWidth, cssHeight: 220, devicePixelRatio: 1 },
  );
  const layout = makeSegmentLayout({
    timelineColumnX: columnX,
    timelineColumnWidthPx: columnWidth,
    rowPaddingPx: 3,
    minWidthPx: 1,
  }).resolve(coords);
  return { coords, layout };
}

describe("projectSegmentRect", () => {
  it("projects a closed segment relative to the timeline column", () => {
    const { coords, layout } = setup();
    const rect = projectSegmentRect({
      segment: makeProjectionEntry("s", 0, 1, 3),
      coords,
      layout,
    });
    expect(rect).not.toBeNull();
    expect(rect!.x).toBeCloseTo(200 + 1 * (600 / 10));
    expect(rect!.width).toBeCloseTo(2 * (600 / 10));
    expect(rect!.y).toBe(3);
    expect(rect!.height).toBe(22 - 6);
  });

  it("clips a segment to the timeline column boundaries", () => {
    const { coords, layout } = setup();
    const rect = projectSegmentRect({
      segment: makeProjectionEntry("s", 0, -5, 50),
      coords,
      layout,
    });
    expect(rect).not.toBeNull();
    expect(rect!.x).toBe(200);
    expect(rect!.width).toBeLessThanOrEqual(600);
    expect(rect!.clippedLeft).toBe(true);
    expect(rect!.clippedRight).toBe(true);
  });

  it("returns null when the segment is entirely outside the visible window", () => {
    const { coords, layout } = setup();
    const rect = projectSegmentRect({
      segment: makeProjectionEntry("s", 0, 50, 60),
      coords,
      layout,
    });
    expect(rect).toBeNull();
  });

  it("enforces the minimum visible width on tiny segments", () => {
    const { coords, layout } = setup();
    const rect = projectSegmentRect({
      segment: makeProjectionEntry("s", 0, 1, 1.0001),
      coords,
      layout,
    });
    expect(rect).not.toBeNull();
    expect(rect!.width).toBeGreaterThanOrEqual(1);
  });

  it("extends active segments to the camera's right edge", () => {
    const { coords, layout } = setup();
    const rect = projectSegmentRect({
      segment: makeProjectionEntry("s", 0, 8, 8, { isActive: true }),
      coords,
      layout,
    });
    expect(rect).not.toBeNull();
    expect(rect!.x + rect!.width).toBeCloseTo(200 + 600, 0);
  });

  it("returns null when the row is above or below the viewport", () => {
    const { coords, layout } = setup({ rowHeight: 22 });
    const above = projectSegmentRect({
      segment: makeProjectionEntry("s", -50, 1, 2),
      coords,
      layout,
    });
    const below = projectSegmentRect({
      segment: makeProjectionEntry("s", 9999, 1, 2),
      coords,
      layout,
    });
    expect(above).toBeNull();
    expect(below).toBeNull();
  });
});

describe("crispStrokeRect", () => {
  it("aligns to half-pixel offsets for crisp strokes", () => {
    const result = crispStrokeRect({
      x: 10.2,
      y: 5.8,
      width: 30.4,
      height: 12.1,
      clippedLeft: false,
      clippedRight: false,
      pixelsPerSecond: 0,
    });
    expect(result.x).toBe(10.5);
    expect(result.y).toBe(6.5);
    expect(result.width).toBe(29);
    expect(result.height).toBe(11);
  });
});
