import { describe, expect, it } from "vitest";
import {
  isUsableRange,
  mergeRanges,
  padRange,
} from "@/dashboard/timeline/zoom/TimelineZoomFocus";

describe("focus helpers", () => {
  it("padRange widens the range by the configured fraction", () => {
    const padded = padRange({ startSeconds: 0, endSeconds: 10 }, 0.1);
    expect(padded.startSeconds).toBeCloseTo(-1);
    expect(padded.endSeconds).toBeCloseTo(11);
  });

  it("mergeRanges returns the smallest enclosing range", () => {
    const merged = mergeRanges([
      { startSeconds: 1, endSeconds: 3 },
      { startSeconds: 5, endSeconds: 7 },
    ]);
    expect(merged).toEqual({ startSeconds: 1, endSeconds: 7 });
  });

  it("mergeRanges returns null when there are no ranges", () => {
    expect(mergeRanges([])).toBeNull();
  });

  it("isUsableRange filters degenerate inputs", () => {
    expect(isUsableRange(null)).toBe(false);
    expect(isUsableRange({ startSeconds: 0, endSeconds: 0 })).toBe(false);
    expect(isUsableRange({ startSeconds: 0, endSeconds: 1 })).toBe(true);
    expect(isUsableRange({ startSeconds: NaN, endSeconds: 1 })).toBe(false);
  });
});
