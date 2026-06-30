import { describe, expect, it } from "vitest";
import {
  cameraKey,
  layoutKey,
  TimelineSegmentGeometryCache,
} from "@/dashboard/timeline/segments/TimelineSegmentCaching";

const fakeRect = {
  x: 0,
  y: 0,
  width: 10,
  height: 10,
  clippedLeft: false,
  clippedRight: false,
  pixelsPerSecond: 1,
};

describe("TimelineSegmentGeometryCache", () => {
  it("stores + retrieves rects by segmentId", () => {
    const cache = new TimelineSegmentGeometryCache();
    cache.syncEpoch("c", "l");
    cache.set("s", fakeRect);
    expect(cache.get("s")).toEqual(fakeRect);
  });

  it("counts hits + misses", () => {
    const cache = new TimelineSegmentGeometryCache();
    cache.syncEpoch("c", "l");
    cache.set("s", fakeRect);
    cache.get("s");
    cache.get("missing");
    expect(cache.hits()).toBe(1);
    expect(cache.misses()).toBe(1);
  });

  it("clears entries when the camera fingerprint changes", () => {
    const cache = new TimelineSegmentGeometryCache();
    cache.syncEpoch("c1", "l");
    cache.set("s", fakeRect);
    cache.syncEpoch("c2", "l");
    expect(cache.get("s")).toBeNull();
  });

  it("evicts the oldest entry when capacity is exceeded", () => {
    const cache = new TimelineSegmentGeometryCache(2);
    cache.syncEpoch("c", "l");
    cache.set("a", fakeRect);
    cache.set("b", fakeRect);
    cache.set("c", fakeRect);
    expect(cache.get("a")).toBeNull();
    expect(cache.get("b")).not.toBeNull();
    expect(cache.get("c")).not.toBeNull();
    expect(cache.evictions()).toBeGreaterThan(0);
  });
});

describe("cameraKey / layoutKey", () => {
  it("are deterministic per identical inputs", () => {
    const camera = { timeStart: 0, timeEnd: 1, rowStart: 0, rowHeight: 20 };
    expect(cameraKey(camera)).toBe(cameraKey(camera));
    expect(
      layoutKey({ timelineColumnX: 0, timelineColumnWidthPx: 100, rowPaddingPx: 2, minWidthPx: 1 }),
    ).toBe(
      layoutKey({ timelineColumnX: 0, timelineColumnWidthPx: 100, rowPaddingPx: 2, minWidthPx: 1 }),
    );
  });

  it("differ when any field changes", () => {
    expect(cameraKey({ timeStart: 0, timeEnd: 1, rowStart: 0, rowHeight: 20 })).not.toBe(
      cameraKey({ timeStart: 0, timeEnd: 2, rowStart: 0, rowHeight: 20 }),
    );
  });
});
