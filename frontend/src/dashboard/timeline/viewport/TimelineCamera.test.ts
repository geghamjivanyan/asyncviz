import { describe, expect, it } from "vitest";
import {
  DEFAULT_CAMERA,
  cameraDuration,
  cameraEqual,
  clampRowStart,
  fitCameraToRange,
  panCamera,
  scrollCamera,
  setRowHeight,
  zoomCameraAroundTime,
} from "@/dashboard/timeline/viewport/TimelineCamera";

describe("TimelineCamera", () => {
  it("cameraEqual returns true for identical state", () => {
    expect(cameraEqual(DEFAULT_CAMERA, { ...DEFAULT_CAMERA })).toBe(true);
  });

  it("cameraEqual returns false on any field change", () => {
    expect(cameraEqual(DEFAULT_CAMERA, { ...DEFAULT_CAMERA, timeEnd: 2 })).toBe(false);
  });

  it("cameraDuration returns positive seconds", () => {
    expect(cameraDuration({ ...DEFAULT_CAMERA, timeStart: 0, timeEnd: 5 })).toBe(5);
  });

  it("cameraDuration never returns zero", () => {
    expect(cameraDuration({ ...DEFAULT_CAMERA, timeStart: 1, timeEnd: 1 })).toBeGreaterThan(0);
  });

  it("panCamera shifts both edges by delta seconds", () => {
    const next = panCamera({ ...DEFAULT_CAMERA, timeStart: 0, timeEnd: 10 }, 3);
    expect(next.timeStart).toBe(3);
    expect(next.timeEnd).toBe(13);
  });

  it("scrollCamera shifts rowStart", () => {
    const next = scrollCamera({ ...DEFAULT_CAMERA, rowStart: 2 }, 4);
    expect(next.rowStart).toBe(6);
  });

  it("setRowHeight clamps to >= 1", () => {
    expect(setRowHeight(DEFAULT_CAMERA, 0.4).rowHeight).toBe(1);
    expect(setRowHeight(DEFAULT_CAMERA, 25).rowHeight).toBe(25);
  });

  it("clampRowStart clamps to [0, totalRows - visibleRows]", () => {
    // Past the bottom — clamps to the last valid start.
    const overflow = { ...DEFAULT_CAMERA, rowStart: 150 };
    expect(clampRowStart(overflow, 10, 100).rowStart).toBe(90);
    // In-range rowStart stays put.
    const inRange = { ...DEFAULT_CAMERA, rowStart: 50 };
    expect(clampRowStart(inRange, 10, 100).rowStart).toBe(50);
    // Tiny dataset — last valid start is 0.
    const tiny = { ...DEFAULT_CAMERA, rowStart: 50 };
    expect(clampRowStart(tiny, 10, 5).rowStart).toBe(0);
    // Negative rowStart clamps to 0.
    const negative = { ...DEFAULT_CAMERA, rowStart: -10 };
    expect(clampRowStart(negative, 10, 100).rowStart).toBe(0);
  });

  it("zoomCameraAroundTime preserves the anchor's relative position", () => {
    const camera = { ...DEFAULT_CAMERA, timeStart: 0, timeEnd: 10 };
    const zoomed = zoomCameraAroundTime(camera, 5, 0.5);
    expect(zoomed.timeEnd - zoomed.timeStart).toBeCloseTo(5);
    // Anchor stayed at the centre.
    expect((zoomed.timeStart + zoomed.timeEnd) / 2).toBeCloseTo(5);
  });

  it("zoomCameraAroundTime clamps the duration", () => {
    const camera = { ...DEFAULT_CAMERA, timeStart: 0, timeEnd: 10 };
    const zoomed = zoomCameraAroundTime(camera, 5, 1e-10, { minDurationSeconds: 0.1 });
    expect(zoomed.timeEnd - zoomed.timeStart).toBeCloseTo(0.1);
  });

  it("zoomCameraAroundTime ignores invalid factors", () => {
    const camera = { ...DEFAULT_CAMERA, timeStart: 0, timeEnd: 10 };
    expect(zoomCameraAroundTime(camera, 5, 0)).toEqual(camera);
    expect(zoomCameraAroundTime(camera, 5, Number.NaN)).toEqual(camera);
  });

  it("fitCameraToRange rejects degenerate ranges", () => {
    const camera = { ...DEFAULT_CAMERA, timeStart: 0, timeEnd: 10 };
    expect(fitCameraToRange(camera, 5, 5)).toEqual(camera);
    expect(fitCameraToRange(camera, 5, 4)).toEqual(camera);
    const fit = fitCameraToRange(camera, 2, 8);
    expect(fit.timeStart).toBe(2);
    expect(fit.timeEnd).toBe(8);
  });
});
