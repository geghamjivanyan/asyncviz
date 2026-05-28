import { describe, expect, it } from "vitest";
import {
  describePanAction,
  describePanState,
} from "@/dashboard/timeline/pan/TimelinePanAccessibility";

const baseState = {
  timeStartSeconds: 0,
  timeEndSeconds: 10,
  durationSeconds: 10,
  pixelsPerSecond: 80,
  dragging: false,
  atMinTime: false,
  atMaxTime: false,
  minTimeSeconds: 0,
  maxTimeSeconds: 100,
  scaleKey: "k",
};

describe("pan a11y helpers", () => {
  it("describes a normal pan state", () => {
    expect(describePanState(baseState)).toContain("Visible range");
  });

  it("flags the at-start edge", () => {
    expect(describePanState({ ...baseState, atMinTime: true })).toContain("start of timeline");
  });

  it("flags the at-end edge", () => {
    expect(describePanState({ ...baseState, atMaxTime: true })).toContain("end of timeline");
  });

  it("formats sub-second times in ms", () => {
    expect(
      describePanState({ ...baseState, timeStartSeconds: 0, timeEndSeconds: 0.5 }),
    ).toContain("ms");
  });

  it("describes pan actions in human language", () => {
    expect(describePanAction("pan-left")).toContain("Panned left");
    expect(describePanAction("pan-right")).toContain("Panned right");
    expect(describePanAction("pan-left-fast")).toContain("fast");
    expect(describePanAction("pan-home")).toContain("start");
    expect(describePanAction("pan-end")).toContain("end");
    expect(describePanAction("center")).toContain("Centered");
    expect(describePanAction("to-time")).toContain("Moved");
  });
});
