import { describe, expect, it } from "vitest";
import { TimelineTimeScale } from "@/dashboard/timeline/scaling/TimelineTimeScale";
import {
  centerAnchor,
  cursorAnchor,
  resolveAnchorTime,
  timeAnchor,
  xAnchor,
} from "@/dashboard/timeline/zoom/TimelineZoomAnchoring";

describe("anchoring", () => {
  const scale = new TimelineTimeScale(0, 10, 100);

  it("time anchor returns the supplied seconds", () => {
    expect(resolveAnchorTime(timeAnchor(3.5), { scale })).toBe(3.5);
  });

  it("x anchor maps screen x to world seconds via the scale", () => {
    expect(resolveAnchorTime(xAnchor(50), { scale })).toBeCloseTo(5);
  });

  it("cursor anchor uses the supplied cursor time when present", () => {
    expect(resolveAnchorTime(cursorAnchor(), { scale, cursorTimeSeconds: 7 })).toBe(7);
  });

  it("cursor anchor falls back to center when no cursor is set", () => {
    expect(resolveAnchorTime(cursorAnchor(), { scale, cursorTimeSeconds: null })).toBeCloseTo(5);
  });

  it("center anchor returns the midpoint", () => {
    expect(resolveAnchorTime(centerAnchor(), { scale })).toBeCloseTo(5);
  });
});
