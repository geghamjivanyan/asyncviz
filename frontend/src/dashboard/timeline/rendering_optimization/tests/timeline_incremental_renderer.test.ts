import { describe, expect, it, vi } from "vitest";
import { TimelineIncrementalRenderer } from "../timeline_incremental_renderer";
import { FULL_REGION_SENTINEL } from "../models";

function makeCtx() {
  return {
    save: vi.fn(),
    restore: vi.fn(),
    beginPath: vi.fn(),
    rect: vi.fn(),
    clip: vi.fn(),
    clearRect: vi.fn(),
  } as unknown as CanvasRenderingContext2D & {
    save: ReturnType<typeof vi.fn>;
    clearRect: ReturnType<typeof vi.fn>;
  };
}

const region = (x = 10, y = 10, width = 50, height = 50) => ({
  x,
  y,
  width,
  height,
  reason: "data" as const,
});

describe("TimelineIncrementalRenderer", () => {
  it("skips when there are no regions", () => {
    const r = new TimelineIncrementalRenderer();
    const result = r.run({
      ctx: makeCtx(),
      cssWidth: 100,
      cssHeight: 100,
      regions: [],
      passes: [{ id: "data", draw: vi.fn() }],
    });
    expect(result.mode).toBe("skip");
    expect(result.passesExecuted).toBe(0);
  });

  it("runs incrementally for normal regions", () => {
    const r = new TimelineIncrementalRenderer();
    const draw = vi.fn();
    const ctx = makeCtx();
    const result = r.run({
      ctx,
      cssWidth: 200,
      cssHeight: 200,
      regions: [region(0, 0, 50, 50)],
      passes: [{ id: "data", draw }],
    });
    expect(result.mode).toBe("incremental");
    expect(draw).toHaveBeenCalledTimes(1);
    expect(ctx.clearRect).toHaveBeenCalledTimes(1);
  });

  it("runs full when a full-region sentinel is present", () => {
    const r = new TimelineIncrementalRenderer();
    const draw = vi.fn();
    const ctx = makeCtx();
    const result = r.run({
      ctx,
      cssWidth: 200,
      cssHeight: 200,
      regions: [FULL_REGION_SENTINEL],
      passes: [{ id: "data", draw }],
    });
    expect(result.mode).toBe("full");
    expect(ctx.clearRect).toHaveBeenCalledWith(0, 0, 200, 200);
  });

  it("clips regions to the canvas bounds", () => {
    const r = new TimelineIncrementalRenderer();
    const draw = vi.fn();
    const ctx = makeCtx();
    const result = r.run({
      ctx,
      cssWidth: 100,
      cssHeight: 100,
      regions: [region(50, 50, 200, 200)],
      passes: [{ id: "data", draw }],
    });
    expect(result.mode).toBe("incremental");
    expect(result.areaPx2).toBeLessThanOrEqual(100 * 100);
  });

  it("catches pass errors + continues", () => {
    const r = new TimelineIncrementalRenderer();
    const ok = vi.fn();
    const bad = vi.fn(() => {
      throw new Error("nope");
    });
    const result = r.run({
      ctx: makeCtx(),
      cssWidth: 100,
      cssHeight: 100,
      regions: [region()],
      passes: [
        { id: "bad", draw: bad },
        { id: "ok", draw: ok },
      ],
    });
    expect(ok).toHaveBeenCalled();
    expect(result.failures).toBe(1);
  });

  it("runs every pass per region", () => {
    const r = new TimelineIncrementalRenderer();
    const draw1 = vi.fn();
    const draw2 = vi.fn();
    r.run({
      ctx: makeCtx(),
      cssWidth: 100,
      cssHeight: 100,
      regions: [region(0, 0, 50, 50), region(40, 0, 50, 50)],
      passes: [
        { id: "a", draw: draw1 },
        { id: "b", draw: draw2 },
      ],
    });
    expect(draw1).toHaveBeenCalledTimes(2);
    expect(draw2).toHaveBeenCalledTimes(2);
  });
});
