import { describe, expect, it } from "vitest";
import { TimelineRowTextCache } from "@/dashboard/timeline/rows/TimelineRowCaching";

describe("TimelineRowTextCache", () => {
  it("stores + retrieves entries by font/width/text", () => {
    const cache = new TimelineRowTextCache();
    cache.set("12px sans", 200, "abc", { text: "abc", widthPx: 18, truncated: false });
    expect(cache.get("12px sans", 200, "abc")?.text).toBe("abc");
  });

  it("returns null + counts a miss when the key is absent", () => {
    const cache = new TimelineRowTextCache();
    expect(cache.get("12px sans", 200, "abc")).toBeNull();
    expect(cache.misses()).toBe(1);
  });

  it("tracks hits + misses", () => {
    const cache = new TimelineRowTextCache();
    cache.set("12px sans", 200, "abc", { text: "abc", widthPx: 18, truncated: false });
    cache.get("12px sans", 200, "abc");
    cache.get("12px sans", 200, "xyz");
    expect(cache.hits()).toBe(1);
    expect(cache.misses()).toBe(1);
  });

  it("evicts the oldest entry when capacity is exceeded", () => {
    const cache = new TimelineRowTextCache(2);
    cache.set("f", 1, "a", { text: "a", widthPx: 1, truncated: false });
    cache.set("f", 1, "b", { text: "b", widthPx: 1, truncated: false });
    cache.set("f", 1, "c", { text: "c", widthPx: 1, truncated: false });
    expect(cache.get("f", 1, "a")).toBeNull();
    expect(cache.get("f", 1, "b")?.text).toBe("b");
    expect(cache.get("f", 1, "c")?.text).toBe("c");
  });
});
