import { describe, expect, it } from "vitest";
import { TimelineProjectionCache } from "../timeline_projection_cache";

describe("TimelineProjectionCache", () => {
  it("returns identical references on repeated reads", () => {
    const c = new TimelineProjectionCache(8);
    const value = { rows: [1, 2, 3] };
    c.set("fp1", value);
    expect(c.get("fp1")).toBe(value);
    expect(c.get("fp1")).toBe(c.get("fp1"));
  });

  it("computes on miss, reuses on hit", () => {
    const c = new TimelineProjectionCache(8);
    let calls = 0;
    const make = () => {
      calls += 1;
      return { rows: [] };
    };
    c.getOrCompute("fp1", make);
    c.getOrCompute("fp1", make);
    c.getOrCompute("fp2", make);
    expect(calls).toBe(2);
  });

  it("evicts LRU when capacity exceeded", () => {
    const c = new TimelineProjectionCache(2);
    c.set("a", { x: 1 });
    c.set("b", { x: 2 });
    c.set("c", { x: 3 });
    expect(c.get("a")).toBeUndefined();
    expect(c.get("b")).toBeDefined();
    expect(c.get("c")).toBeDefined();
  });

  it("reports reuse hits separately from LRU hits", () => {
    const c = new TimelineProjectionCache(8);
    c.set("fp", { x: 1 });
    c.get("fp");
    c.get("fp");
    expect(c.stats().reuseHits).toBe(2);
  });
});
