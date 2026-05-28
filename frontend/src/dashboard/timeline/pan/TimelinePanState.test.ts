import { describe, expect, it } from "vitest";
import { buildPanState } from "@/dashboard/timeline/pan/TimelinePanState";
import { buildEngine } from "@/dashboard/timeline/pan/__fixtures__/makePanFixtures";

describe("buildPanState", () => {
  it("captures the engine's current scale", () => {
    const engine = buildEngine({ timeStart: 0, timeEnd: 10 });
    const state = buildPanState(engine);
    expect(state.timeStartSeconds).toBe(0);
    expect(state.timeEndSeconds).toBe(10);
    expect(state.durationSeconds).toBe(10);
  });

  it("honors supplied bounds", () => {
    const engine = buildEngine();
    const state = buildPanState(engine, { minTimeSeconds: 0, maxTimeSeconds: 10 });
    expect(state.atMinTime).toBe(true);
    expect(state.atMaxTime).toBe(true);
  });

  it("flags drag state passed in", () => {
    const engine = buildEngine();
    const state = buildPanState(engine, undefined, true);
    expect(state.dragging).toBe(true);
  });
});
