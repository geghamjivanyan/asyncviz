import { describe, expect, it, vi } from "vitest";
import { TimelineDrawBatcher } from "../timeline_draw_batcher";

function fakeCtx() {
  return {
    fillStyle: "",
    strokeStyle: "",
    lineWidth: 1,
    fillRect: vi.fn(),
    strokeRect: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
  } as unknown as CanvasRenderingContext2D & {
    fillRect: ReturnType<typeof vi.fn>;
    strokeRect: ReturnType<typeof vi.fn>;
    stroke: ReturnType<typeof vi.fn>;
  };
}

describe("TimelineDrawBatcher", () => {
  it("groups same-style rects + flushes one style change", () => {
    const b = new TimelineDrawBatcher(1024);
    const ctx = fakeCtx();
    b.enqueueRect("#fff", { kind: "rect", x: 0, y: 0, width: 1, height: 1 });
    b.enqueueRect("#fff", { kind: "rect", x: 1, y: 1, width: 1, height: 1 });
    b.enqueueRect("#000", { kind: "rect", x: 2, y: 2, width: 1, height: 1 });
    b.flush(ctx);
    expect(ctx.fillRect).toHaveBeenCalledTimes(3);
    expect(b.stats().styleSwitches).toBe(1);
  });

  it("dispatches stroke rects", () => {
    const b = new TimelineDrawBatcher(1024);
    const ctx = fakeCtx();
    b.enqueueStrokeRect("#000", {
      kind: "stroke-rect",
      x: 0,
      y: 0,
      width: 5,
      height: 5,
      lineWidth: 2,
    });
    b.flush(ctx);
    expect(ctx.strokeRect).toHaveBeenCalledTimes(1);
    expect(ctx.lineWidth).toBe(2);
  });

  it("dispatches lines", () => {
    const b = new TimelineDrawBatcher(1024);
    const ctx = fakeCtx();
    b.enqueueLine("#000", {
      kind: "line",
      x0: 0,
      y0: 0,
      x1: 10,
      y1: 0,
      lineWidth: 1,
    });
    b.flush(ctx);
    expect(ctx.stroke).toHaveBeenCalledTimes(1);
  });

  it("respects capacity + tracks overflow drops", () => {
    const b = new TimelineDrawBatcher(2);
    b.enqueueRect("#fff", { kind: "rect", x: 0, y: 0, width: 1, height: 1 });
    b.enqueueRect("#fff", { kind: "rect", x: 1, y: 0, width: 1, height: 1 });
    b.enqueueRect("#fff", { kind: "rect", x: 2, y: 0, width: 1, height: 1 });
    expect(b.bufferedOpCount()).toBe(2);
    expect(b.stats().droppedOnOverflow).toBe(1);
  });

  it("ignores zero-area rects", () => {
    const b = new TimelineDrawBatcher(8);
    b.enqueueRect("#fff", { kind: "rect", x: 0, y: 0, width: 0, height: 5 });
    expect(b.bufferedOpCount()).toBe(0);
    expect(b.stats().opsEnqueued).toBe(0);
  });

  it("reset clears buffers but not stats", () => {
    const b = new TimelineDrawBatcher(8);
    b.enqueueRect("#fff", { kind: "rect", x: 0, y: 0, width: 1, height: 1 });
    b.reset();
    expect(b.bufferedOpCount()).toBe(0);
    expect(b.stats().opsEnqueued).toBe(1);
  });
});
