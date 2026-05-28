import { describe, expect, it } from "vitest";
import {
  computeFreezeGeometry,
  cullVisibleFreezeRegions,
  MIN_FREEZE_PIXEL_WIDTH,
  pointInGeometry,
  snapMarkerX,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionGeometry";
import { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import { makeFreezeRegionView } from "@/dashboard/timeline/freeze_regions/__fixtures__/makeFreezeRegionFixtures";

function coords(timeStart: number, timeEnd: number, cssWidth = 1000) {
  return new TimelineCoordinateSystem(
    { timeStart, timeEnd, rowStart: 0, rowHeight: 18 },
    { cssWidth, cssHeight: 400, devicePixelRatio: 1 },
  );
}

describe("computeFreezeGeometry", () => {
  it("returns null for freezes entirely outside the visible window", () => {
    const c = coords(10, 20);
    const region = makeFreezeRegionView({ startSeconds: 0, endSeconds: 5 });
    expect(computeFreezeGeometry(region, c)).toBeNull();
  });

  it("returns full geometry for a freeze entirely inside the window", () => {
    const c = coords(0, 10);
    const region = makeFreezeRegionView({ startSeconds: 2, endSeconds: 4 });
    const geom = computeFreezeGeometry(region, c);
    expect(geom).not.toBeNull();
    expect(geom!.fullyVisible).toBe(true);
    expect(geom!.clippedLeft).toBe(false);
    expect(geom!.clippedRight).toBe(false);
    expect(geom!.xStart).toBeCloseTo(200);
    expect(geom!.xEnd).toBeCloseTo(400);
  });

  it("marks clipped-left for freezes starting before the window", () => {
    const c = coords(5, 10);
    const region = makeFreezeRegionView({ startSeconds: 3, endSeconds: 7 });
    const geom = computeFreezeGeometry(region, c);
    expect(geom).not.toBeNull();
    expect(geom!.clippedLeft).toBe(true);
    expect(geom!.xStart).toBe(0);
  });

  it("marks clipped-right for freezes ending after the window", () => {
    const c = coords(5, 10);
    const region = makeFreezeRegionView({ startSeconds: 7, endSeconds: 14 });
    const geom = computeFreezeGeometry(region, c);
    expect(geom).not.toBeNull();
    expect(geom!.clippedRight).toBe(true);
    expect(geom!.xEnd).toBe(1000);
  });

  it("enforces the minimum pixel width for collapsed freezes", () => {
    const c = coords(0, 1000);
    const region = makeFreezeRegionView({ startSeconds: 100, endSeconds: 100 });
    const geom = computeFreezeGeometry(region, c);
    expect(geom).not.toBeNull();
    expect(geom!.width).toBeGreaterThanOrEqual(MIN_FREEZE_PIXEL_WIDTH);
  });

  it("returns null when the viewport has zero width", () => {
    const c = coords(0, 10, 0);
    const region = makeFreezeRegionView({ startSeconds: 1, endSeconds: 2 });
    expect(computeFreezeGeometry(region, c)).toBeNull();
  });
});

describe("cullVisibleFreezeRegions", () => {
  it("returns only regions intersecting the visible window, preserving order", () => {
    const c = coords(0, 10);
    const a = makeFreezeRegionView({ groupId: "a", startSeconds: 0, endSeconds: 2 });
    const b = makeFreezeRegionView({ groupId: "b", startSeconds: 5, endSeconds: 6 });
    const c2 = makeFreezeRegionView({ groupId: "c", startSeconds: 100, endSeconds: 200 });
    const result = cullVisibleFreezeRegions([a, b, c2], c);
    expect(result.map((r) => r.region.groupId)).toEqual(["a", "b"]);
  });
});

describe("pointInGeometry", () => {
  it("returns true for x inside the body", () => {
    const region = makeFreezeRegionView();
    const c = coords(0, 10);
    const geom = computeFreezeGeometry(region, c)!;
    expect(pointInGeometry(geom, (geom.xStart + geom.xEnd) / 2)).toBe(true);
  });

  it("returns false for x outside the body", () => {
    const region = makeFreezeRegionView();
    const c = coords(0, 10);
    const geom = computeFreezeGeometry(region, c)!;
    expect(pointInGeometry(geom, geom.xStart - 1)).toBe(false);
    expect(pointInGeometry(geom, geom.xEnd + 1)).toBe(false);
  });
});

describe("snapMarkerX", () => {
  it("snaps to half-pixel for crisp 1-px strokes", () => {
    expect(snapMarkerX(10.4)).toBe(10.5);
    expect(snapMarkerX(10.6)).toBe(11.5);
  });
});
