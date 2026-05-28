import { describe, expect, it } from "vitest";
import { TimelineGeometryCache } from "../timeline_geometry_cache";

describe("TimelineGeometryCache", () => {
  it("caches geometry under the active version", () => {
    const c = new TimelineGeometryCache(16);
    c.set("seg:1", { x: 0, y: 0, width: 10, height: 10 });
    expect(c.get("seg:1")).toEqual({ x: 0, y: 0, width: 10, height: 10 });
  });

  it("bumpVersion invalidates every cached entry", () => {
    const c = new TimelineGeometryCache(16);
    c.set("seg:1", { x: 0, y: 0, width: 10, height: 10 });
    c.bumpVersion();
    expect(c.get("seg:1")).toBeUndefined();
    expect(c.stats().versionResets).toBe(1);
  });

  it("getOrCompute caches on miss", () => {
    const c = new TimelineGeometryCache(16);
    let calls = 0;
    const compute = () => {
      calls += 1;
      return { x: 1, y: 2, width: 3, height: 4 };
    };
    c.getOrCompute("seg:1", compute);
    c.getOrCompute("seg:1", compute);
    expect(calls).toBe(1);
  });

  it("quantizes sub-pixel coords", () => {
    const c = new TimelineGeometryCache(16);
    c.set("seg:1", { x: 0.4, y: 0.6, width: 10.2, height: 10.7 });
    const entry = c.get("seg:1")!;
    expect(entry.x).toBe(0.5);
    expect(entry.y).toBe(0.5);
    expect(entry.width).toBe(10);
    expect(entry.height).toBe(10.5);
  });

  it("evicts least-recently-used entries", () => {
    const c = new TimelineGeometryCache(2);
    c.set("a", { x: 0, y: 0, width: 1, height: 1 });
    c.set("b", { x: 0, y: 0, width: 1, height: 1 });
    c.set("c", { x: 0, y: 0, width: 1, height: 1 });
    expect(c.get("a")).toBeUndefined();
    expect(c.get("b")).toBeDefined();
    expect(c.get("c")).toBeDefined();
  });

  it("reports LRU stats", () => {
    const c = new TimelineGeometryCache(4);
    c.set("a", { x: 0, y: 0, width: 1, height: 1 });
    c.get("a");
    c.get("missing");
    const s = c.stats();
    expect(s.hits).toBe(1);
    expect(s.misses).toBe(1);
    expect(s.hitRatio).toBeCloseTo(0.5);
  });

  it("clears the entire cache + retains version", () => {
    const c = new TimelineGeometryCache(4);
    c.bumpVersion();
    c.set("a", { x: 0, y: 0, width: 1, height: 1 });
    c.clear();
    expect(c.get("a")).toBeUndefined();
    expect(c.currentVersion()).toBe(1);
  });

  it("clamps negative width/height to zero", () => {
    const c = new TimelineGeometryCache(4);
    c.set("a", { x: 0, y: 0, width: -5, height: -3 });
    const e = c.get("a")!;
    expect(e.width).toBe(0);
    expect(e.height).toBe(0);
  });
});
