import { describe, expect, it } from "vitest";
import {
  clampPanTimeStart,
  mergeBounds,
  panWouldExceedBound,
  viewportEdgeState,
} from "@/dashboard/timeline/pan/TimelinePanConstraints";

const bounds = { minTimeSeconds: 0, maxTimeSeconds: 100 };

describe("pan constraints", () => {
  it("mergeBounds defaults to unbounded", () => {
    expect(mergeBounds(undefined)).toEqual({
      minTimeSeconds: null,
      maxTimeSeconds: null,
    });
  });

  it("mergeBounds preserves provided bounds", () => {
    expect(mergeBounds({ minTimeSeconds: 5 })).toEqual({
      minTimeSeconds: 5,
      maxTimeSeconds: null,
    });
  });

  it("clampPanTimeStart respects both edges", () => {
    expect(
      clampPanTimeStart(-5, {
        timeStartSeconds: 0,
        durationSeconds: 10,
        bounds,
      }),
    ).toBe(0);
    expect(
      clampPanTimeStart(200, {
        timeStartSeconds: 0,
        durationSeconds: 10,
        bounds,
      }),
    ).toBe(90);
  });

  it("panWouldExceedBound detects breaches", () => {
    expect(
      panWouldExceedBound(-5, {
        timeStartSeconds: 0,
        durationSeconds: 10,
        bounds,
      }),
    ).toBe("min");
    expect(
      panWouldExceedBound(100, {
        timeStartSeconds: 0,
        durationSeconds: 10,
        bounds,
      }),
    ).toBe("max");
    expect(
      panWouldExceedBound(5, {
        timeStartSeconds: 0,
        durationSeconds: 10,
        bounds,
      }),
    ).toBeNull();
  });

  it("viewportEdgeState fires at the bounds", () => {
    expect(
      viewportEdgeState({
        timeStartSeconds: 0,
        durationSeconds: 10,
        bounds,
      }).atMin,
    ).toBe(true);
    expect(
      viewportEdgeState({
        timeStartSeconds: 90,
        durationSeconds: 10,
        bounds,
      }).atMax,
    ).toBe(true);
  });
});
