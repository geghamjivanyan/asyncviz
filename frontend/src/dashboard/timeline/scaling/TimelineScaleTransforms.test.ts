import { describe, expect, it } from "vitest";
import { TimelineTimeScale } from "@/dashboard/timeline/scaling/TimelineTimeScale";
import {
  fitScaleToRange,
  panScale,
  zoomScaleAroundTime,
  zoomScaleAroundX,
} from "@/dashboard/timeline/scaling/TimelineScaleTransforms";

describe("scale transforms", () => {
  it("panScale shifts both edges by deltaSeconds", () => {
    const scale = new TimelineTimeScale(0, 10, 100);
    expect(panScale(scale, 5)).toEqual({ timeStart: 5, timeEnd: 15 });
  });

  it("zoomScaleAroundTime keeps the anchor at the same fractional position", () => {
    const scale = new TimelineTimeScale(0, 10, 100);
    const zoomed = zoomScaleAroundTime(scale, 5, 0.5); // zoom in 2x around the middle
    expect(zoomed.timeStart).toBeCloseTo(2.5);
    expect(zoomed.timeEnd).toBeCloseTo(7.5);
  });

  it("zoomScaleAroundX delegates to the time-anchor variant", () => {
    const scale = new TimelineTimeScale(0, 10, 100);
    const fromTime = zoomScaleAroundTime(scale, 5, 0.5);
    const fromX = zoomScaleAroundX(scale, 50, 0.5);
    expect(fromX.timeStart).toBeCloseTo(fromTime.timeStart);
    expect(fromX.timeEnd).toBeCloseTo(fromTime.timeEnd);
  });

  it("zoomScaleAroundTime returns the scale unchanged when factor is invalid", () => {
    const scale = new TimelineTimeScale(0, 10, 100);
    expect(zoomScaleAroundTime(scale, 5, 0)).toEqual({ timeStart: 0, timeEnd: 10 });
    expect(zoomScaleAroundTime(scale, 5, -1)).toEqual({ timeStart: 0, timeEnd: 10 });
    expect(zoomScaleAroundTime(scale, 5, Number.POSITIVE_INFINITY).timeEnd).toBeGreaterThan(0);
  });

  it("fitScaleToRange snaps the window exactly to [start, end]", () => {
    const scale = new TimelineTimeScale(0, 10, 100);
    expect(fitScaleToRange(scale, 2, 6)).toEqual({ timeStart: 2, timeEnd: 6 });
    expect(fitScaleToRange(scale, 5, 5)).toEqual({ timeStart: 0, timeEnd: 10 });
  });
});
