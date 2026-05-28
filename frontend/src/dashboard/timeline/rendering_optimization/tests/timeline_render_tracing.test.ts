import { beforeEach, describe, expect, it } from "vitest";
import {
  clearRenderOptimizationTrace,
  getRenderOptimizationTrace,
  isRenderOptimizationTraceEnabled,
  recordRenderOptimizationTrace,
  setRenderOptimizationTraceEnabled,
  RENDER_OPT_TRACE_CAPACITY,
} from "../timeline_render_tracing";

describe("render-optimization tracing", () => {
  beforeEach(() => {
    setRenderOptimizationTraceEnabled(false);
    clearRenderOptimizationTrace();
  });

  it("is disabled by default", () => {
    expect(isRenderOptimizationTraceEnabled()).toBe(false);
  });

  it("ignores records while disabled", () => {
    recordRenderOptimizationTrace("frame", "ignored");
    expect(getRenderOptimizationTrace()).toHaveLength(0);
  });

  it("records when enabled", () => {
    setRenderOptimizationTraceEnabled(true);
    recordRenderOptimizationTrace("frame", "ok");
    const trace = getRenderOptimizationTrace();
    expect(trace).toHaveLength(1);
    expect(trace[0]!.kind).toBe("frame");
    expect(trace[0]!.detail).toBe("ok");
  });

  it("caps at the ring capacity", () => {
    setRenderOptimizationTraceEnabled(true);
    for (let i = 0; i < RENDER_OPT_TRACE_CAPACITY + 5; i += 1) {
      recordRenderOptimizationTrace("frame", `f${i}`);
    }
    expect(getRenderOptimizationTrace().length).toBe(RENDER_OPT_TRACE_CAPACITY);
  });

  it("clears when disabling", () => {
    setRenderOptimizationTraceEnabled(true);
    recordRenderOptimizationTrace("frame", "x");
    setRenderOptimizationTraceEnabled(false);
    expect(getRenderOptimizationTrace()).toHaveLength(0);
  });
});
