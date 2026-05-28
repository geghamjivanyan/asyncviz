import { describe, expect, it } from "vitest";
import { TimelineViewportCuller } from "../timeline_viewport_culling";
import { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";

function makeCoords() {
  return new TimelineCoordinateSystem(
    { timeStart: 0, timeEnd: 10, rowStart: 0, rowHeight: 20 },
    { cssWidth: 1000, cssHeight: 200, devicePixelRatio: 1 },
  );
}

describe("TimelineViewportCuller", () => {
  it("retains items inside the visible window", () => {
    const c = new TimelineViewportCuller(0);
    const items = [
      { startSeconds: 1, endSeconds: 2, rowIndex: 0 },
      { startSeconds: 4, endSeconds: 6, rowIndex: 5 },
    ];
    const out = c.cull(makeCoords(), items);
    expect(out).toHaveLength(2);
  });

  it("culls items outside the time range", () => {
    const c = new TimelineViewportCuller(0);
    const items = [
      { startSeconds: -5, endSeconds: -1, rowIndex: 0 },
      { startSeconds: 100, endSeconds: 101, rowIndex: 0 },
    ];
    const out = c.cull(makeCoords(), items);
    expect(out).toHaveLength(0);
    expect(c.stats().cullRatio).toBe(1);
  });

  it("culls items outside the row range", () => {
    const c = new TimelineViewportCuller(0);
    const items = [
      { startSeconds: 1, endSeconds: 2, rowIndex: -5 },
      { startSeconds: 1, endSeconds: 2, rowIndex: 100 },
    ];
    const out = c.cull(makeCoords(), items);
    expect(out).toHaveLength(0);
  });

  it("respects the overscan band", () => {
    const c = new TimelineViewportCuller(200);
    const coords = makeCoords();
    const items = [
      { startSeconds: -1.5, endSeconds: -1.0, rowIndex: 0 },
    ];
    const out = c.cull(coords, items);
    expect(out).toHaveLength(1);
  });

  it("reports cull ratio", () => {
    const c = new TimelineViewportCuller(0);
    const items = [
      { startSeconds: 1, endSeconds: 2, rowIndex: 0 },
      { startSeconds: 1000, endSeconds: 2000, rowIndex: 0 },
    ];
    c.cull(makeCoords(), items);
    expect(c.stats().cullRatio).toBeCloseTo(0.5);
  });

  it("isRowVisible reflects the visible band", () => {
    const c = new TimelineViewportCuller(0);
    const coords = makeCoords();
    expect(c.isRowVisible(coords, 5)).toBe(true);
    expect(c.isRowVisible(coords, 999)).toBe(false);
  });

  it("isTimeVisible reflects the visible band", () => {
    const c = new TimelineViewportCuller(0);
    const coords = makeCoords();
    expect(c.isTimeVisible(coords, 2, 3)).toBe(true);
    expect(c.isTimeVisible(coords, 100, 200)).toBe(false);
  });
});
