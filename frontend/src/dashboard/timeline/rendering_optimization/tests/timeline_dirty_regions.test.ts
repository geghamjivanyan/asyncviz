import { describe, expect, it } from "vitest";
import { TimelineDirtyRegionTracker } from "../timeline_dirty_regions";
import { FULL_REGION_SENTINEL } from "../models";

const region = (x: number, y: number, w: number, h: number) => ({
  x,
  y,
  width: w,
  height: h,
  reason: "data" as const,
});

describe("TimelineDirtyRegionTracker", () => {
  it("starts empty + reports clean", () => {
    const t = new TimelineDirtyRegionTracker(8);
    expect(t.isDirty()).toBe(false);
    expect(t.snapshot()).toHaveLength(0);
  });

  it("rejects non-positive capacity", () => {
    expect(() => new TimelineDirtyRegionTracker(0)).toThrow(RangeError);
  });

  it("tracks distinct regions", () => {
    const t = new TimelineDirtyRegionTracker(8);
    t.invalidate(region(0, 0, 10, 10));
    t.invalidate(region(100, 100, 10, 10));
    expect(t.snapshot()).toHaveLength(2);
    expect(t.isDirty()).toBe(true);
  });

  it("merges overlapping regions", () => {
    const t = new TimelineDirtyRegionTracker(8);
    t.invalidate(region(0, 0, 20, 20));
    t.invalidate(region(10, 10, 20, 20));
    const snap = t.snapshot();
    expect(snap).toHaveLength(1);
    expect(snap[0]!.x).toBe(0);
    expect(snap[0]!.y).toBe(0);
    expect(snap[0]!.width).toBe(30);
    expect(snap[0]!.height).toBe(30);
  });

  it("collapses to a full redraw when capacity exceeded", () => {
    const t = new TimelineDirtyRegionTracker(3);
    for (let i = 0; i < 6; i += 1) {
      t.invalidate(region(i * 100, 0, 10, 10));
    }
    const snap = t.snapshot();
    expect(snap).toHaveLength(1);
    expect(snap[0]!.width).toBe(FULL_REGION_SENTINEL.width);
    expect(t.stats().full).toBe(true);
    expect(t.stats().collapses).toBeGreaterThanOrEqual(1);
  });

  it("invalidateFull collapses immediately", () => {
    const t = new TimelineDirtyRegionTracker(8);
    t.invalidate(region(0, 0, 10, 10));
    t.invalidateFull("viewport");
    expect(t.stats().full).toBe(true);
  });

  it("flush resets state + returns the snapshot", () => {
    const t = new TimelineDirtyRegionTracker(8);
    t.invalidate(region(0, 0, 5, 5));
    const flushed = t.flush();
    expect(flushed).toHaveLength(1);
    expect(t.isDirty()).toBe(false);
    expect(t.snapshot()).toHaveLength(0);
  });

  it("tracks invalidations by reason", () => {
    const t = new TimelineDirtyRegionTracker(8);
    t.invalidate(region(0, 0, 10, 10));
    t.invalidate({ ...region(0, 0, 10, 10), reason: "camera" });
    const stats = t.stats();
    expect(stats.byReason.data).toBe(1);
    expect(stats.byReason.camera).toBe(1);
  });

  it("ignores zero-dimension regions", () => {
    const t = new TimelineDirtyRegionTracker(8);
    t.invalidate(region(0, 0, 0, 10));
    t.invalidate(region(0, 0, 10, 0));
    expect(t.isDirty()).toBe(false);
  });
});
