import { describe, expect, it } from "vitest";
import { TimelineVirtualizationCache } from "@/dashboard/timeline/virtualization/TimelineVirtualizationCache";
import type { VirtualizationFrame } from "@/dashboard/timeline/virtualization/models/TimelineVirtualizationModels";

const stubWindow = {
  rows: { startIndex: 0, endIndex: 1, overscanStartIndex: 0, overscanEndIndex: 1, totalRows: 1 },
  time: { startSeconds: 0, endSeconds: 1, overscanStartSeconds: 0, overscanEndSeconds: 1 },
  key: "k",
  resolvedAtMs: 0,
};

function frame<T extends string>(key: T): VirtualizationFrame<unknown, unknown> {
  return {
    window: { ...stubWindow, key },
    rows: [],
    segments: [],
    rowsConsidered: 0,
    segmentsConsidered: 0,
    fromCache: false,
  };
}

describe("TimelineVirtualizationCache", () => {
  it("returns null on miss + records miss metrics", () => {
    const cache = new TimelineVirtualizationCache();
    cache.syncSequence(1);
    expect(cache.get("absent")).toBeNull();
    expect(cache.metrics().misses).toBe(1);
  });

  it("returns the cached frame + records hit metrics", () => {
    const cache = new TimelineVirtualizationCache();
    cache.syncSequence(1);
    const f = frame("k");
    cache.set("k", f);
    expect(cache.get("k")).toBe(f);
    expect(cache.metrics().hits).toBe(1);
  });

  it("clears every entry when the sequence advances", () => {
    const cache = new TimelineVirtualizationCache();
    cache.syncSequence(1);
    cache.set("k", frame("k"));
    cache.syncSequence(2);
    expect(cache.get("k")).toBeNull();
  });

  it("evicts the oldest entry when capacity is exceeded", () => {
    const cache = new TimelineVirtualizationCache(2);
    cache.syncSequence(1);
    cache.set("a", frame("a"));
    cache.set("b", frame("b"));
    cache.set("c", frame("c"));
    expect(cache.get("a")).toBeNull();
    expect(cache.get("b")).not.toBeNull();
    expect(cache.get("c")).not.toBeNull();
    expect(cache.metrics().evictions).toBeGreaterThan(0);
  });
});
