import { describe, expect, it } from "vitest";
import { hitTest } from "@/dashboard/timeline/interaction/TimelineHitTesting";
import { makeCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";

const camera = { timeStart: 0, timeEnd: 10, rowStart: 0, rowHeight: 20 };
const viewport = { cssWidth: 1000, cssHeight: 100, devicePixelRatio: 1 };

describe("hitTest", () => {
  it("returns the matching row + segment", () => {
    const coords = makeCoordinateSystem(camera, viewport);
    const result = hitTest({
      xCss: 250,
      yCss: 10,
      coords,
      rows: [{ rowIndex: 0, taskId: "a", label: "A" }],
      segments: [
        {
          segmentId: "s1",
          rowIndex: 0,
          taskId: "a",
          startSeconds: 2,
          endSeconds: 5,
          intent: "run",
          isActive: false,
        },
      ],
    });
    expect(result.row?.taskId).toBe("a");
    expect(result.segment?.segmentId).toBe("s1");
    expect(result.timeSeconds).toBeCloseTo(2.5);
  });

  it("returns null segment when the pointer misses every segment in the row", () => {
    const coords = makeCoordinateSystem(camera, viewport);
    const result = hitTest({
      xCss: 100,
      yCss: 10,
      coords,
      rows: [{ rowIndex: 0, taskId: "a", label: "A" }],
      segments: [
        {
          segmentId: "s1",
          rowIndex: 0,
          taskId: "a",
          startSeconds: 5,
          endSeconds: 8,
          intent: "run",
          isActive: false,
        },
      ],
    });
    expect(result.row?.taskId).toBe("a");
    expect(result.segment).toBeNull();
  });

  it("returns null row when the pointer is below the rendered rows", () => {
    const coords = makeCoordinateSystem(camera, viewport);
    const result = hitTest({
      xCss: 100,
      yCss: 1000,
      coords,
      rows: [{ rowIndex: 0, taskId: "a", label: "A" }],
      segments: [],
    });
    expect(result.row).toBeNull();
    expect(result.segment).toBeNull();
  });
});
