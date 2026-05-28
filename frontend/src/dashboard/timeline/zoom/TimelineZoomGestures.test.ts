import { describe, expect, it } from "vitest";
import {
  pinchToZoomFactor,
  stepsToZoomFactor,
  wheelToZoomFactor,
} from "@/dashboard/timeline/zoom/TimelineZoomGestures";
import { DEFAULT_ZOOM_CONFIG } from "@/dashboard/timeline/zoom/models/TimelineZoomModels";

describe("zoom gestures", () => {
  it("wheelToZoomFactor returns >1 for positive deltaY", () => {
    const factor = wheelToZoomFactor({ deltaY: 100, deltaMode: "pixel" });
    expect(factor).toBeGreaterThan(1);
  });

  it("wheelToZoomFactor returns <1 for negative deltaY", () => {
    const factor = wheelToZoomFactor({ deltaY: -100, deltaMode: "pixel" });
    expect(factor).toBeLessThan(1);
  });

  it("wheelToZoomFactor returns ≈1 for zero deltaY", () => {
    expect(wheelToZoomFactor({ deltaY: 0, deltaMode: "pixel" })).toBe(1);
  });

  it("line mode scales by the configured line height", () => {
    const lineFactor = wheelToZoomFactor({ deltaY: 1, deltaMode: "line" });
    const pixelFactor = wheelToZoomFactor({
      deltaY: DEFAULT_ZOOM_CONFIG.wheelLinePx,
      deltaMode: "line",
    });
    expect(pixelFactor).toBeGreaterThan(lineFactor);
  });

  it("pinchToZoomFactor inverts the pinch ratio", () => {
    expect(pinchToZoomFactor(2)).toBeCloseTo(0.5);
    expect(pinchToZoomFactor(0.5)).toBeCloseTo(2);
    expect(pinchToZoomFactor(0)).toBe(1);
  });

  it("stepsToZoomFactor zooms in for negative steps and out for positive", () => {
    const inFactor = stepsToZoomFactor(-1);
    const outFactor = stepsToZoomFactor(1);
    expect(inFactor).toBeLessThan(1);
    expect(outFactor).toBeGreaterThan(1);
    expect(stepsToZoomFactor(0)).toBe(1);
  });
});
