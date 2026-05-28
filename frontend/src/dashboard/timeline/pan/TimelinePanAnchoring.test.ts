import { describe, expect, it } from "vitest";
import {
  isPastClickThreshold,
  makeDragAnchor,
  timeStartFromAnchor,
} from "@/dashboard/timeline/pan/TimelinePanAnchoring";

describe("pan anchoring", () => {
  it("makeDragAnchor captures the supplied state", () => {
    const anchor = makeDragAnchor({
      pointerXCss: 100,
      pointerTimeSeconds: 5,
      timeStartSeconds: 0,
      timeEndSeconds: 10,
      atMs: 1234,
    });
    expect(anchor.pointerXCss).toBe(100);
    expect(anchor.pointerTimeSeconds).toBe(5);
    expect(anchor.initialTimeStartSeconds).toBe(0);
    expect(anchor.startedAtMs).toBe(1234);
  });

  it("timeStartFromAnchor inverts the pointer delta", () => {
    const anchor = makeDragAnchor({
      pointerXCss: 100,
      pointerTimeSeconds: 5,
      timeStartSeconds: 0,
      timeEndSeconds: 10,
      atMs: 0,
    });
    // pointer moved +50px (right) ⇒ viewport moves -0.5s (left)
    expect(timeStartFromAnchor(anchor, 150, 0.01)).toBeCloseTo(-0.5);
    // pointer moved -50px (left) ⇒ viewport moves +0.5s (right)
    expect(timeStartFromAnchor(anchor, 50, 0.01)).toBeCloseTo(0.5);
  });

  it("isPastClickThreshold filters tiny pointer wiggle", () => {
    const anchor = makeDragAnchor({
      pointerXCss: 100,
      pointerTimeSeconds: 5,
      timeStartSeconds: 0,
      timeEndSeconds: 10,
      atMs: 0,
    });
    expect(isPastClickThreshold(anchor, 101)).toBe(false);
    expect(isPastClickThreshold(anchor, 105)).toBe(true);
  });
});
