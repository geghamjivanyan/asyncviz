import { describe, expect, it } from "vitest";
import {
  describeZoomAction,
  describeZoomState,
} from "@/dashboard/timeline/zoom/TimelineZoomAccessibility";

const baseState = {
  durationSeconds: 5,
  level: 0.5,
  atMin: false,
  atMax: false,
  minDurationSeconds: 1,
  maxDurationSeconds: 10,
  pixelsPerSecond: 100,
  scaleKey: "k",
};

describe("zoom a11y helpers", () => {
  it("describes a normal zoom state", () => {
    const text = describeZoomState(baseState);
    expect(text).toContain("zoom level 50%");
    expect(text).toContain("Visible duration");
  });

  it("describes the at-min edge", () => {
    expect(describeZoomState({ ...baseState, atMin: true })).toContain("minimum zoom");
  });

  it("describes the at-max edge", () => {
    expect(describeZoomState({ ...baseState, atMax: true })).toContain("maximum zoom");
  });

  it("formats sub-second durations in milliseconds", () => {
    expect(describeZoomState({ ...baseState, durationSeconds: 0.05 })).toContain("ms");
  });

  it("formats sub-millisecond durations in microseconds", () => {
    expect(describeZoomState({ ...baseState, durationSeconds: 1e-5 })).toContain("µs");
  });

  it("describes zoom actions in human language", () => {
    expect(describeZoomAction("zoom-in")).toContain("Zoomed in");
    expect(describeZoomAction("zoom-out")).toContain("Zoomed out");
    expect(describeZoomAction("zoom-reset")).toContain("Zoom reset");
    expect(describeZoomAction("fit-all")).toContain("Fit");
  });
});
