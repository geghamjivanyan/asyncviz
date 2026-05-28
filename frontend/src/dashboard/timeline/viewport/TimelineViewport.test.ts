import { describe, expect, it } from "vitest";
import {
  EMPTY_VIEWPORT,
  viewportBackingHeight,
  viewportBackingWidth,
  viewportEqual,
  viewportFromElement,
} from "@/dashboard/timeline/viewport/TimelineViewport";

describe("TimelineViewport", () => {
  it("viewportFromElement clamps negatives + invalid DPR", () => {
    const v = viewportFromElement(-1, -1, -2);
    expect(v.cssWidth).toBe(0);
    expect(v.cssHeight).toBe(0);
    expect(v.devicePixelRatio).toBe(1);
  });

  it("viewportFromElement keeps valid input", () => {
    const v = viewportFromElement(500, 250, 2);
    expect(v.cssWidth).toBe(500);
    expect(v.cssHeight).toBe(250);
    expect(v.devicePixelRatio).toBe(2);
  });

  it("viewportEqual is true for identical viewports", () => {
    expect(viewportEqual(EMPTY_VIEWPORT, EMPTY_VIEWPORT)).toBe(true);
    expect(viewportEqual(EMPTY_VIEWPORT, { ...EMPTY_VIEWPORT, cssWidth: 1 })).toBe(false);
  });

  it("viewportBacking*: scales by DPR", () => {
    const v = viewportFromElement(100, 200, 2);
    expect(viewportBackingWidth(v)).toBe(200);
    expect(viewportBackingHeight(v)).toBe(400);
  });
});
