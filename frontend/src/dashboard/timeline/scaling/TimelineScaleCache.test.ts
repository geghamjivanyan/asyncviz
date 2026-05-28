import { describe, expect, it } from "vitest";
import { TimelineScaleTickCache } from "@/dashboard/timeline/scaling/TimelineScaleCache";

const stubList = {
  ticks: [],
  majorIntervalSeconds: 1,
  minorIntervalSeconds: 0.2,
  key: "k",
};

describe("TimelineScaleTickCache", () => {
  it("returns null on miss and counts the miss", () => {
    const cache = new TimelineScaleTickCache();
    expect(cache.get("absent")).toBeNull();
    expect(cache.metrics().misses).toBe(1);
  });

  it("returns the cached list on hit and counts the hit", () => {
    const cache = new TimelineScaleTickCache();
    cache.set("k", { ...stubList, key: "k" });
    expect(cache.get("k")?.key).toBe("k");
    expect(cache.metrics().hits).toBe(1);
  });

  it("evicts the oldest entry when capacity is exceeded", () => {
    const cache = new TimelineScaleTickCache(2);
    cache.set("a", { ...stubList, key: "a" });
    cache.set("b", { ...stubList, key: "b" });
    cache.set("c", { ...stubList, key: "c" });
    expect(cache.get("a")).toBeNull();
    expect(cache.get("b")?.key).toBe("b");
    expect(cache.get("c")?.key).toBe("c");
    expect(cache.metrics().evictions).toBeGreaterThan(0);
  });

  it("clear empties the cache", () => {
    const cache = new TimelineScaleTickCache();
    cache.set("k", stubList);
    cache.clear();
    expect(cache.size()).toBe(0);
    expect(cache.get("k")).toBeNull();
  });
});
