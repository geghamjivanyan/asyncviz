import { describe, expect, it } from "vitest";
import { buildZoomState } from "@/dashboard/timeline/zoom/TimelineZoomState";
import { buildEngine } from "@/dashboard/timeline/zoom/__fixtures__/makeZoomFixtures";

describe("buildZoomState", () => {
  it("computes a normalized level inside [0, 1]", () => {
    const engine = buildEngine({ timeStart: 0, timeEnd: 10 });
    const state = buildZoomState(engine);
    expect(state.level).toBeGreaterThanOrEqual(0);
    expect(state.level).toBeLessThanOrEqual(1);
  });

  it("level 0 when the visible window is the maximum duration", () => {
    const engine = buildEngine({ timeStart: 0, timeEnd: 1000, maxDurationSeconds: 1000 });
    const state = buildZoomState(engine);
    expect(state.level).toBeCloseTo(0);
    expect(state.atMax).toBe(true);
  });

  it("level 1 when the visible window is the minimum duration", () => {
    const engine = buildEngine({ timeStart: 0, timeEnd: 1, minDurationSeconds: 1 });
    const state = buildZoomState(engine);
    expect(state.level).toBeCloseTo(1);
    expect(state.atMin).toBe(true);
  });
});
