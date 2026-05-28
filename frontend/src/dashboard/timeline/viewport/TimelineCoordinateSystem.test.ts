import { describe, expect, it } from "vitest";
import { makeCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";

const camera = { timeStart: 0, timeEnd: 10, rowStart: 0, rowHeight: 20 };
const viewport = { cssWidth: 1000, cssHeight: 400, devicePixelRatio: 1 };

describe("TimelineCoordinateSystem", () => {
  it("timeToX scales by pixelsPerSecond", () => {
    const c = makeCoordinateSystem(camera, viewport);
    expect(c.pixelsPerSecond).toBe(100);
    expect(c.timeToX(0)).toBe(0);
    expect(c.timeToX(5)).toBe(500);
    expect(c.timeToX(10)).toBe(1000);
  });

  it("xToTime inverts timeToX", () => {
    const c = makeCoordinateSystem(camera, viewport);
    expect(c.xToTime(0)).toBe(0);
    expect(c.xToTime(500)).toBe(5);
  });

  it("rowToY/yToRow round-trip", () => {
    const c = makeCoordinateSystem(camera, viewport);
    expect(c.rowToY(0)).toBe(0);
    expect(c.rowToY(3)).toBe(60);
    expect(c.yToRow(60)).toBe(3);
  });

  it("visibleRowRange clips to totalRows", () => {
    const c = makeCoordinateSystem(camera, viewport);
    const range = c.visibleRowRange(50);
    // 400px / 20px = 20 rows fit; we render 21 (slop) clipped to total.
    expect(range.startIndex).toBe(0);
    expect(range.endIndex).toBeLessThanOrEqual(50);
    expect(range.endIndex - range.startIndex).toBeLessThanOrEqual(22);
  });

  it("segmentSpan returns null when outside the viewport", () => {
    const c = makeCoordinateSystem(camera, viewport);
    expect(c.segmentSpan(-5, -4)).toBeNull();
    expect(c.segmentSpan(20, 30)).toBeNull();
  });

  it("segmentSpan clips at the viewport edges", () => {
    const c = makeCoordinateSystem(camera, viewport);
    const span = c.segmentSpan(-1, 5)!;
    expect(span.x0).toBe(0);
    expect(span.x1).toBe(500);
  });

  it("segmentSpan enforces a minimum sub-pixel width", () => {
    const c = makeCoordinateSystem(camera, viewport);
    const span = c.segmentSpan(5, 5)!;
    expect(span.width).toBeGreaterThan(0);
  });

  it("intersectsTime + intersectsRow return correct booleans", () => {
    const c = makeCoordinateSystem(camera, viewport);
    expect(c.intersectsTime(-1, 0.5)).toBe(true);
    expect(c.intersectsTime(20, 25)).toBe(false);
    expect(c.intersectsRow(5)).toBe(true);
    expect(c.intersectsRow(100)).toBe(false);
  });

  it("pointToWorld returns null outside the viewport", () => {
    const c = makeCoordinateSystem(camera, viewport);
    expect(c.pointToWorld(-1, 0)).toBeNull();
    expect(c.pointToWorld(0, -1)).toBeNull();
    expect(c.pointToWorld(2000, 0)).toBeNull();
  });

  it("pointToWorld returns (time, row) for valid points", () => {
    const c = makeCoordinateSystem(camera, viewport);
    const world = c.pointToWorld(100, 40);
    expect(world).not.toBeNull();
    expect(world!.time).toBeCloseTo(1);
    expect(world!.rowIndex).toBeCloseTo(2);
  });
});
