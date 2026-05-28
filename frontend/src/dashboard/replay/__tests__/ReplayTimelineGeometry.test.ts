import { describe, expect, it } from "vitest";

import {
  clamp,
  fractionToSequence,
  pixelToSequence,
  sequenceInViewport,
  sequenceToFraction,
  sequenceToPixel,
  sequenceToTimestamp,
  timestampToSequence,
  viewportForWindow,
} from "@/dashboard/replay/ReplayTimelineGeometry";
import type {
  ReplaySessionWindow,
  ReplayTimelineViewport,
} from "@/dashboard/replay/models/ReplayTimelineModels";

const viewport: ReplayTimelineViewport = {
  startSequence: 0,
  endSequence: 100,
  widthPx: 1000,
};

const window: ReplaySessionWindow = {
  minSequence: 0,
  maxSequence: 100,
  minMonotonicNs: 0,
  maxMonotonicNs: 1_000_000,
};

describe("clamp", () => {
  it("returns input within bounds", () => {
    expect(clamp(5, 0, 10)).toBe(5);
  });
  it("clamps below low", () => {
    expect(clamp(-1, 0, 10)).toBe(0);
  });
  it("clamps above high", () => {
    expect(clamp(11, 0, 10)).toBe(10);
  });
  it("collapses NaN to low", () => {
    expect(clamp(NaN, 5, 10)).toBe(5);
  });
});

describe("sequenceToPixel / pixelToSequence", () => {
  it("maps 0 → 0 and max → width", () => {
    expect(sequenceToPixel(0, viewport)).toBe(0);
    expect(sequenceToPixel(100, viewport)).toBe(1000);
  });
  it("round-trips through pixelToSequence", () => {
    const px = sequenceToPixel(50, viewport);
    expect(pixelToSequence(px, viewport)).toBe(50);
  });
  it("clamps inputs at the viewport bounds", () => {
    expect(sequenceToPixel(-10, viewport)).toBe(0);
    expect(sequenceToPixel(999, viewport)).toBe(1000);
  });
  it("returns 0 when widthPx is 0", () => {
    expect(sequenceToPixel(50, { ...viewport, widthPx: 0 })).toBe(0);
  });
});

describe("sequenceToFraction / fractionToSequence", () => {
  it("round-trips at midpoint", () => {
    const frac = sequenceToFraction(50, window);
    expect(frac).toBeCloseTo(0.5);
    expect(fractionToSequence(frac, window)).toBe(50);
  });
  it("returns 0 for empty window", () => {
    expect(
      sequenceToFraction(5, {
        minSequence: 0,
        maxSequence: 0,
        minMonotonicNs: 0,
        maxMonotonicNs: 0,
      }),
    ).toBe(0);
  });
});

describe("timestampToSequence / sequenceToTimestamp", () => {
  it("round-trips at midpoint", () => {
    const ts = sequenceToTimestamp(50, window);
    expect(timestampToSequence(ts, window)).toBe(50);
  });
});

describe("sequenceInViewport", () => {
  it("respects inclusive bounds", () => {
    expect(sequenceInViewport(0, viewport)).toBe(true);
    expect(sequenceInViewport(100, viewport)).toBe(true);
    expect(sequenceInViewport(101, viewport)).toBe(false);
  });
});

describe("viewportForWindow", () => {
  it("derives a viewport spanning the window", () => {
    const vp = viewportForWindow(window, 400);
    expect(vp.startSequence).toBe(0);
    expect(vp.endSequence).toBe(100);
    expect(vp.widthPx).toBe(400);
  });
});
