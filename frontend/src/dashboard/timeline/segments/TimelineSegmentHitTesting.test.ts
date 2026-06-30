import { describe, expect, it } from "vitest";
import { hitTestSegment } from "@/dashboard/timeline/segments/TimelineSegmentHitTesting";
import { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import { makeSegmentLayout } from "@/dashboard/timeline/segments/TimelineSegmentLayout";
import { makeProjectionEntry } from "@/dashboard/timeline/segments/__fixtures__/makeSegment";

function setup() {
  const coords = new TimelineCoordinateSystem(
    { timeStart: 0, timeEnd: 10, rowStart: 0, rowHeight: 20 },
    { cssWidth: 800, cssHeight: 200, devicePixelRatio: 1 },
  );
  const layout = makeSegmentLayout({
    timelineColumnX: 200,
    timelineColumnWidthPx: 600,
  }).resolve(coords);
  const entries = [
    makeProjectionEntry("a", 0, 1, 4),
    makeProjectionEntry("b", 0, 3, 6, { lifecycleState: "waiting" }),
    makeProjectionEntry("c", 1, 7, 9),
  ];
  return { coords, layout, entries };
}

describe("hitTestSegment", () => {
  it("returns null segment when the pointer is outside the timeline column", () => {
    const { coords, layout, entries } = setup();
    const result = hitTestSegment({ xCss: 50, yCss: 10, coords, layout, entries });
    expect(result.segment).toBeNull();
    expect(result.timeSeconds).toBeNull();
  });

  it("locates the segment under the pointer", () => {
    const { coords, layout, entries } = setup();
    // x=200 corresponds to camera time 0, x=380 to time 3.
    const result = hitTestSegment({ xCss: 380, yCss: 5, coords, layout, entries });
    expect(result.segment).not.toBeNull();
    // Both "a" (1..4) and "b" (3..6) cover time=3 — overlap-safe rule
    // says the segment with the *later* start wins (b).
    expect(result.segment!.segmentId).toBe("b");
  });

  it("returns the active segment when the pointer is past the wire end", () => {
    const { coords, layout } = setup();
    const entries = [makeProjectionEntry("active", 0, 8, 8, { isActive: true })];
    const result = hitTestSegment({
      xCss: 200 + 60 * 9,
      yCss: 5,
      coords,
      layout,
      entries,
    });
    expect(result.segment?.segmentId).toBe("active");
  });

  it("reports the world time at the pointer", () => {
    const { coords, layout, entries } = setup();
    const result = hitTestSegment({ xCss: 260, yCss: 5, coords, layout, entries });
    expect(result.timeSeconds).not.toBeNull();
    expect(result.timeSeconds!).toBeCloseTo(1);
  });
});
