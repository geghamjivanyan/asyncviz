import { describe, expect, it } from "vitest";
import { TimelineCanvasPool, type CanvasFactory } from "../timeline_canvas_pool";

const stubFactory: CanvasFactory = {
  create(w, h) {
    return { tag: "canvas", w, h };
  },
};

describe("TimelineCanvasPool", () => {
  it("returns a new canvas on first acquire", () => {
    const pool = new TimelineCanvasPool(4, stubFactory);
    const c = pool.acquire(100, 50);
    expect(c.width).toBe(100);
    expect(c.height).toBe(50);
  });

  it("reuses released canvases of the same size", () => {
    const pool = new TimelineCanvasPool(4, stubFactory);
    const c1 = pool.acquire(100, 50);
    pool.release(c1);
    const c2 = pool.acquire(100, 50);
    expect(c2.canvas).toBe(c1.canvas);
    expect(pool.stats().reuseHits).toBe(1);
  });

  it("allocates fresh on different dimensions", () => {
    const pool = new TimelineCanvasPool(4, stubFactory);
    const a = pool.acquire(100, 50);
    pool.release(a);
    const b = pool.acquire(200, 50);
    expect(b.canvas).not.toBe(a.canvas);
  });

  it("evicts free entries when over capacity", () => {
    const pool = new TimelineCanvasPool(2, stubFactory);
    const a = pool.acquire(100, 50);
    const b = pool.acquire(200, 50);
    pool.release(a);
    pool.release(b);
    const c = pool.acquire(300, 50);
    expect(c.width).toBe(300);
    expect(pool.stats().evictions).toBeGreaterThanOrEqual(1);
  });

  it("release of unknown canvas is a no-op", () => {
    const pool = new TimelineCanvasPool(4, stubFactory);
    expect(() => pool.release({ width: 1, height: 1, canvas: {} })).not.toThrow();
  });

  it("clear empties + resets stats", () => {
    const pool = new TimelineCanvasPool(4, stubFactory);
    const c = pool.acquire(100, 50);
    pool.release(c);
    pool.clear();
    expect(pool.stats().size).toBe(0);
    expect(pool.stats().hits).toBe(0);
  });

  it("rejects non-positive capacity", () => {
    expect(() => new TimelineCanvasPool(0, stubFactory)).toThrow(RangeError);
  });
});
