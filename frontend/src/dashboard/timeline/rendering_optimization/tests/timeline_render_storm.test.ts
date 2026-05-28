/**
 * Storm + recovery + replay-flood + giant-timeline simulations.
 *
 * These tests don't measure FPS (the test runner can't), but they do
 * measure structural properties: under storm load the optimizer must
 * (a) degrade, (b) bound dirty-region growth, (c) keep critical
 * passes drawing, (d) recover once load drops.
 */

import { describe, expect, it, vi } from "vitest";
import {
  TimelineRenderScheduler,
  RenderPriority,
  default_config,
  RenderOptimizationMetrics,
  type PipelineDrawHooks,
} from "..";

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

function makeHooks(latencyMs = 0): PipelineDrawHooks {
  return {
    drawPass: vi.fn(() => {
      if (latencyMs > 0) busy(latencyMs);
    }),
    drawOverlay: vi.fn(),
  };
}

function busy(ms: number) {
  const start = performance.now();
  while (performance.now() - start < ms) {
    // burn CPU
  }
}

describe("render-optimization storm sims", () => {
  it("survives a giant-timeline flood without exploding the dirty set", () => {
    const s = new TimelineRenderScheduler({
      config: { ...default_config(), dirtyRegionCapacity: 16 },
      metrics: new RenderOptimizationMetrics(),
    });
    s.registerLayer({
      id: "data",
      priority: RenderPriority.NORMAL,
      invalidatedBy: new Set(["data"]),
      label: "data",
    });
    for (let i = 0; i < 10_000; i += 1) {
      s.invalidateRegion({
        x: i % 1000,
        y: (i * 7) % 500,
        width: 5,
        height: 5,
        reason: "data",
      });
    }
    expect(s.diagnostics().dirty.regionCount).toBeLessThanOrEqual(1);
    expect(s.diagnostics().dirty.full).toBe(true);
  });

  it("preserves CRITICAL passes under degradation", () => {
    const s = new TimelineRenderScheduler({
      config: {
        ...default_config(),
        frameBudgetMs: 1,
        frameBudgetHardMs: 2,
        degradeAfterFrames: 1,
        restoreAfterFrames: 999,
      },
      metrics: new RenderOptimizationMetrics(),
    });
    s.registerLayer({
      id: "data",
      priority: RenderPriority.IDLE,
      invalidatedBy: new Set(["data"]),
      label: "idle data",
    });
    s.registerLayer({
      id: "critical",
      priority: RenderPriority.CRITICAL,
      invalidatedBy: new Set(["data"]),
      label: "critical",
    });
    const hooks = makeHooks(3);
    for (let i = 0; i < 6; i += 1) {
      s.invalidateRegion({ x: 0, y: 0, width: 50, height: 50, reason: "data" });
      s.flushRenderPass(makeCtx(), 200, 200, hooks);
    }
    const lastPassCallArgs = (hooks.drawPass as ReturnType<typeof vi.fn>).mock.calls.map(
      (c) => c[0],
    );
    expect(lastPassCallArgs).toContain("critical");
  });

  it("degrades + restores around a transient spike", () => {
    const metrics = new RenderOptimizationMetrics();
    const s = new TimelineRenderScheduler({
      config: {
        ...default_config(),
        frameBudgetMs: 1,
        frameBudgetHardMs: 2,
        degradeAfterFrames: 2,
        restoreAfterFrames: 3,
      },
      metrics,
    });
    s.registerLayer({
      id: "data",
      priority: RenderPriority.NORMAL,
      invalidatedBy: new Set(["data"]),
      label: "data",
    });
    // Hot spike — three slow frames.
    for (let i = 0; i < 4; i += 1) {
      s.invalidateRegion({ x: 0, y: 0, width: 50, height: 50, reason: "data" });
      s.flushRenderPass(makeCtx(), 200, 200, makeHooks(5));
    }
    expect(metrics.snapshot().degradeEvents).toBeGreaterThanOrEqual(1);
    // Cool down — several fast frames.
    for (let i = 0; i < 5; i += 1) {
      s.invalidateRegion({ x: 0, y: 0, width: 1, height: 1, reason: "data" });
      s.flushRenderPass(makeCtx(), 200, 200, makeHooks(0));
    }
    expect(metrics.snapshot().restoreEvents).toBeGreaterThanOrEqual(1);
  });

  it("coalesces a replay-flood of cursor ticks", () => {
    const s = new TimelineRenderScheduler({ metrics: new RenderOptimizationMetrics() });
    s.registerLayer({
      id: "data",
      priority: RenderPriority.NORMAL,
      invalidatedBy: new Set(["data", "replay"]),
      label: "data",
    });
    for (let i = 0; i < 200; i += 1) {
      s.recordCursorTick({ sequence: i, timeSeconds: i * 0.01 });
    }
    s.emitCursorRegion({ y: 0, height: 100 });
    expect(s.replayCoordinator().stats().coalescedTicks).toBe(199);
  });

  it("bounded memory under repeated invalidate/flush cycles", () => {
    const s = new TimelineRenderScheduler({
      config: { ...default_config(), dirtyRegionCapacity: 8 },
      metrics: new RenderOptimizationMetrics(),
    });
    s.registerLayer({
      id: "data",
      priority: RenderPriority.NORMAL,
      invalidatedBy: new Set(["data"]),
      label: "data",
    });
    for (let i = 0; i < 200; i += 1) {
      s.invalidateRegion({
        x: (i * 17) % 800,
        y: (i * 13) % 500,
        width: 5,
        height: 5,
        reason: "data",
      });
      s.flushRenderPass(makeCtx(), 800, 500, makeHooks());
    }
    expect(s.diagnostics().dirty.regionCount).toBeLessThanOrEqual(1);
  });

  it("deterministic redraw ordering given identical inputs", () => {
    const collect = () => {
      const s = new TimelineRenderScheduler({ metrics: new RenderOptimizationMetrics() });
      s.registerLayer({
        id: "a",
        priority: RenderPriority.NORMAL,
        invalidatedBy: new Set(["data"]),
        label: "a",
      });
      s.registerLayer({
        id: "b",
        priority: RenderPriority.HIGH,
        invalidatedBy: new Set(["data"]),
        label: "b",
      });
      const order: string[] = [];
      const hooks: PipelineDrawHooks = {
        drawPass: (id) => order.push(id),
        drawOverlay: vi.fn(),
      };
      s.invalidateRegion({ x: 0, y: 0, width: 50, height: 50, reason: "data" });
      s.flushRenderPass(makeCtx(), 200, 200, hooks);
      return order;
    };
    const a = collect();
    const b = collect();
    expect(a).toEqual(b);
    expect(a[0]).toBe("b"); // HIGH first
  });
});
