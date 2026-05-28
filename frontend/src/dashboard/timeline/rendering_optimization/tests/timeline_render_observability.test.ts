import { describe, expect, it } from "vitest";
import {
  RenderOptimizationMetrics,
  getRenderOptimizationMetrics,
  resetRenderOptimizationMetrics,
} from "../timeline_render_observability";

describe("RenderOptimizationMetrics", () => {
  it("starts zeroed", () => {
    const m = new RenderOptimizationMetrics();
    const s = m.snapshot();
    expect(s.framesRendered).toBe(0);
    expect(s.framesSkipped).toBe(0);
    Object.values(s.invalidationsByReason).forEach((v) => expect(v).toBe(0));
  });

  it("records frames", () => {
    const m = new RenderOptimizationMetrics();
    m.recordFrame({
      mode: "incremental",
      durationMs: 8,
      overBudget: false,
      overHardBudget: false,
      areaPx2: 100,
      canvasAreaPx2: 1000,
    });
    const s = m.snapshot();
    expect(s.framesRendered).toBe(1);
    expect(s.framesIncremental).toBe(1);
    expect(s.dirtyAreaRedrawnPx2).toBe(100);
    expect(s.redrawAreaRatioMean).toBeCloseTo(0.1);
  });

  it("records full mode separately", () => {
    const m = new RenderOptimizationMetrics();
    m.recordFrame({
      mode: "full",
      durationMs: 8,
      overBudget: false,
      overHardBudget: false,
      areaPx2: 1000,
      canvasAreaPx2: 1000,
    });
    expect(m.snapshot().framesFull).toBe(1);
  });

  it("classifies skipped frames", () => {
    const m = new RenderOptimizationMetrics();
    m.recordFrame({
      mode: "skip",
      durationMs: 0,
      overBudget: false,
      overHardBudget: false,
      areaPx2: 0,
      canvasAreaPx2: 0,
    });
    expect(m.snapshot().framesSkipped).toBe(1);
  });

  it("counts over-budget frames", () => {
    const m = new RenderOptimizationMetrics();
    m.recordFrame({
      mode: "incremental",
      durationMs: 30,
      overBudget: true,
      overHardBudget: true,
      areaPx2: 0,
      canvasAreaPx2: 1000,
    });
    const s = m.snapshot();
    expect(s.framesOverBudget).toBe(1);
    expect(s.framesOverHard).toBe(1);
  });

  it("counts dirty region processing", () => {
    const m = new RenderOptimizationMetrics();
    m.recordDirtyRegions(3, 1);
    const s = m.snapshot();
    expect(s.dirtyRegionsProcessed).toBe(3);
    expect(s.dirtyRegionsCollapsed).toBe(1);
  });

  it("counts pass outcomes", () => {
    const m = new RenderOptimizationMetrics();
    m.recordPass({ executed: true, skipped: false, errored: false });
    m.recordPass({ executed: false, skipped: true, errored: false });
    m.recordPass({ executed: false, skipped: false, errored: true });
    const s = m.snapshot();
    expect(s.passesExecuted).toBe(1);
    expect(s.passesSkipped).toBe(1);
    expect(s.passesErrored).toBe(1);
  });

  it("tracks invalidations by reason", () => {
    const m = new RenderOptimizationMetrics();
    m.recordInvalidation("camera");
    m.recordInvalidation("data");
    m.recordInvalidation("camera");
    expect(m.snapshot().invalidationsByReason.camera).toBe(2);
  });

  it("singleton reset wipes state", () => {
    const m = getRenderOptimizationMetrics();
    m.recordFrame({
      mode: "incremental",
      durationMs: 5,
      overBudget: false,
      overHardBudget: false,
      areaPx2: 0,
      canvasAreaPx2: 1,
    });
    resetRenderOptimizationMetrics();
    expect(getRenderOptimizationMetrics().snapshot().framesRendered).toBe(0);
  });
});
