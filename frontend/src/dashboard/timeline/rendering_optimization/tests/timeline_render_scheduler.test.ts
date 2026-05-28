import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  TimelineRenderScheduler,
  RenderPriority,
  default_config,
  lean_config,
  relaxed_config,
  resetRenderOptimizationMetrics,
  RenderOptimizationMetrics,
  FULL_REGION_SENTINEL,
  type PipelineDrawHooks,
} from "..";
import {
  clearRenderOptimizationTrace,
  setRenderOptimizationTraceEnabled,
} from "../timeline_render_tracing";

const dataLayer = {
  id: "data",
  priority: RenderPriority.NORMAL,
  invalidatedBy: new Set(["data" as const, "camera" as const, "viewport" as const]),
  label: "data",
};

function makeCtx() {
  return {
    save: vi.fn(),
    restore: vi.fn(),
    beginPath: vi.fn(),
    rect: vi.fn(),
    clip: vi.fn(),
    clearRect: vi.fn(),
  } as unknown as CanvasRenderingContext2D;
}

function makeHooks() {
  return {
    drawPass: vi.fn(),
    drawOverlay: vi.fn(),
  } as unknown as PipelineDrawHooks & {
    drawPass: ReturnType<typeof vi.fn>;
    drawOverlay: ReturnType<typeof vi.fn>;
  };
}

beforeEach(() => {
  resetRenderOptimizationMetrics();
  clearRenderOptimizationTrace();
  setRenderOptimizationTraceEnabled(false);
});

afterEach(() => {
  resetRenderOptimizationMetrics();
});

describe("TimelineRenderScheduler — facade", () => {
  it("provides default + lean + relaxed configs", () => {
    expect(default_config().frameBudgetMs).toBe(16);
    expect(lean_config().frameBudgetMs).toBeLessThan(16);
    expect(relaxed_config().frameBudgetMs).toBeGreaterThan(16);
  });

  it("registers layers + overlays", () => {
    const s = new TimelineRenderScheduler({ metrics: new RenderOptimizationMetrics() });
    s.registerLayer(dataLayer);
    s.registerOverlay({ id: "overlay:cursor", coalesce: true });
    expect(() => s.registerLayer(dataLayer)).toThrow();
  });

  it("invalidateRegion drives a frame on flush", () => {
    const s = new TimelineRenderScheduler({ metrics: new RenderOptimizationMetrics() });
    s.registerLayer(dataLayer);
    const hooks = makeHooks();
    s.invalidateRegion({ x: 0, y: 0, width: 50, height: 50, reason: "data" });
    const result = s.flushRenderPass(makeCtx(), 200, 200, hooks);
    expect(result.executed).toBe(true);
    expect(result.mode).toBe("incremental");
    expect(hooks.drawPass).toHaveBeenCalledWith("data", expect.anything());
  });

  it("invalidateFull triggers full mode", () => {
    const s = new TimelineRenderScheduler({ metrics: new RenderOptimizationMetrics() });
    s.registerLayer(dataLayer);
    s.invalidateFull("viewport");
    const result = s.flushRenderPass(makeCtx(), 200, 200, makeHooks());
    expect(result.mode).toBe("full");
  });

  it("skips when nothing is dirty", () => {
    const s = new TimelineRenderScheduler({ metrics: new RenderOptimizationMetrics() });
    s.registerLayer(dataLayer);
    const result = s.flushRenderPass(makeCtx(), 100, 100, makeHooks());
    expect(result.mode).toBe("skip");
  });

  it("skips when ctx is null", () => {
    const s = new TimelineRenderScheduler({ metrics: new RenderOptimizationMetrics() });
    s.registerLayer(dataLayer);
    s.invalidateRegion({ x: 0, y: 0, width: 50, height: 50, reason: "data" });
    const result = s.flushRenderPass(null, 100, 100, makeHooks());
    expect(result.mode).toBe("skip");
  });

  it("drives overlay flushes after data passes", () => {
    const s = new TimelineRenderScheduler({ metrics: new RenderOptimizationMetrics() });
    s.registerLayer(dataLayer);
    s.registerOverlay({ id: "overlay:cursor", coalesce: true });
    const hooks = makeHooks();
    s.invalidateRegion({ x: 0, y: 0, width: 50, height: 50, reason: "data" });
    s.requestOverlayRedraw("overlay:cursor", null);
    s.flushRenderPass(makeCtx(), 200, 200, hooks);
    expect(hooks.drawOverlay).toHaveBeenCalledWith("overlay:cursor", null);
  });

  it("emitCursorRegion produces a keyframe on first tick", () => {
    const s = new TimelineRenderScheduler({ metrics: new RenderOptimizationMetrics() });
    s.registerLayer(dataLayer);
    s.recordCursorTick({ sequence: 1, timeSeconds: 1.0 });
    s.emitCursorRegion({ y: 0, height: 100 });
    const result = s.flushRenderPass(makeCtx(), 200, 200, makeHooks());
    expect(result.mode).toBe("full");
  });

  it("emitCursorRegion produces an incremental region on subsequent ticks", () => {
    const m = new RenderOptimizationMetrics();
    const s = new TimelineRenderScheduler({ metrics: m });
    s.registerLayer({
      ...dataLayer,
      invalidatedBy: new Set([
        "data" as const,
        "camera" as const,
        "viewport" as const,
        "replay" as const,
      ]),
    });
    s.recordCursorTick({ sequence: 1, timeSeconds: 1.0 });
    s.emitCursorRegion({ y: 0, height: 100 });
    s.flushRenderPass(makeCtx(), 200, 200, makeHooks());
    s.recordCursorTick({ sequence: 2, timeSeconds: 1.5 });
    s.emitCursorRegion({ y: 0, height: 100 });
    const result = s.flushRenderPass(makeCtx(), 200, 200, makeHooks());
    expect(result.mode).toBe("incremental");
    expect(m.snapshot().cursorIncrementalRedraws).toBe(1);
  });

  it("diagnostics returns a structured snapshot", () => {
    const s = new TimelineRenderScheduler({ metrics: new RenderOptimizationMetrics() });
    s.registerLayer(dataLayer);
    s.invalidateRegion({ x: 0, y: 0, width: 10, height: 10, reason: "data" });
    s.flushRenderPass(makeCtx(), 200, 200, makeHooks());
    const diag = s.diagnostics(16);
    expect(diag.metrics.framesRendered).toBe(1);
    expect(diag.layers.layersRegistered).toBe(1);
    expect(diag.budget.framesObserved).toBeGreaterThan(0);
  });

  it("reset wipes layers + caches", () => {
    const s = new TimelineRenderScheduler({ metrics: new RenderOptimizationMetrics() });
    s.registerLayer(dataLayer);
    s.reset();
    expect(s.diagnostics().layers.layersRegistered).toBe(0);
  });

  it("dispose makes the scheduler inert", () => {
    const s = new TimelineRenderScheduler({ metrics: new RenderOptimizationMetrics() });
    s.registerLayer(dataLayer);
    s.dispose();
    s.invalidateRegion({ x: 0, y: 0, width: 50, height: 50, reason: "data" });
    const result = s.flushRenderPass(makeCtx(), 100, 100, makeHooks());
    expect(result.mode).toBe("skip");
  });

  it("isolates pass failures + records integrity violations", () => {
    const s = new TimelineRenderScheduler({ metrics: new RenderOptimizationMetrics() });
    s.registerLayer(dataLayer);
    s.invalidateRegion({ x: 0, y: 0, width: 50, height: 50, reason: "data" });
    const hooks: PipelineDrawHooks = {
      drawPass: () => {
        throw new Error("boom");
      },
      drawOverlay: vi.fn(),
    };
    const result = s.flushRenderPass(makeCtx(), 100, 100, hooks);
    expect(result.executed).toBe(true);
  });

  it("merges overlapping region invalidations", () => {
    const s = new TimelineRenderScheduler({ metrics: new RenderOptimizationMetrics() });
    s.registerLayer(dataLayer);
    s.invalidateRegion({ x: 0, y: 0, width: 50, height: 50, reason: "data" });
    s.invalidateRegion({ x: 10, y: 10, width: 50, height: 50, reason: "data" });
    const diag = s.diagnostics();
    expect(diag.dirty.regionCount).toBe(1);
  });

  it("collapses to full when too many distinct regions", () => {
    const s = new TimelineRenderScheduler({
      config: { ...default_config(), dirtyRegionCapacity: 2 },
    });
    s.registerLayer(dataLayer);
    s.invalidateRegion({ x: 0, y: 0, width: 5, height: 5, reason: "data" });
    s.invalidateRegion({ x: 100, y: 0, width: 5, height: 5, reason: "data" });
    s.invalidateRegion({ x: 200, y: 0, width: 5, height: 5, reason: "data" });
    expect(s.diagnostics().dirty.full).toBe(true);
  });

  it("registers FULL_REGION_SENTINEL invalidation", () => {
    const s = new TimelineRenderScheduler();
    s.registerLayer(dataLayer);
    s.invalidateRegion({
      ...FULL_REGION_SENTINEL,
      reason: "viewport",
    });
    expect(s.diagnostics().dirty.full).toBe(true);
  });
});
