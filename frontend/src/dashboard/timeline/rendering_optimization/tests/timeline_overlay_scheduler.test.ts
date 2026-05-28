import { describe, expect, it } from "vitest";
import { TimelineOverlayScheduler } from "../timeline_overlay_scheduler";

const region = {
  x: 0,
  y: 0,
  width: 10,
  height: 10,
  reason: "cursor" as const,
};

describe("TimelineOverlayScheduler", () => {
  it("registers + tracks overlays", () => {
    const s = new TimelineOverlayScheduler();
    s.register({ id: "cursor", coalesce: true });
    s.requestOverlayRedraw("cursor", region);
    expect(s.isDirty()).toBe(true);
    expect(s.pendingOverlays()).toEqual(["cursor"]);
  });

  it("coalesces repeated requests for coalescible overlays", () => {
    const s = new TimelineOverlayScheduler();
    s.register({ id: "cursor", coalesce: true });
    s.requestOverlayRedraw("cursor", region);
    s.requestOverlayRedraw("cursor", { ...region, x: 100 });
    expect(s.stats().coalesced).toBe(1);
  });

  it("does not coalesce when coalesce is false", () => {
    const s = new TimelineOverlayScheduler();
    s.register({ id: "selection", coalesce: false });
    s.requestOverlayRedraw("selection", region);
    s.requestOverlayRedraw("selection", region);
    expect(s.stats().coalesced).toBe(0);
  });

  it("flush drains the dirty set", () => {
    const s = new TimelineOverlayScheduler();
    s.register({ id: "cursor", coalesce: true });
    s.requestOverlayRedraw("cursor", region);
    const drained = s.flush();
    expect(drained).toHaveLength(1);
    expect(drained[0]!.id).toBe("cursor");
    expect(s.isDirty()).toBe(false);
  });

  it("flush merges coalesced regions", () => {
    const s = new TimelineOverlayScheduler();
    s.register({ id: "cursor", coalesce: true });
    s.requestOverlayRedraw("cursor", region);
    s.requestOverlayRedraw("cursor", { ...region, x: 50 });
    const drained = s.flush();
    expect(drained[0]!.region!.width).toBeGreaterThan(region.width);
  });

  it("unregister removes an overlay", () => {
    const s = new TimelineOverlayScheduler();
    s.register({ id: "cursor", coalesce: true });
    s.unregister("cursor");
    s.requestOverlayRedraw("cursor", region);
    expect(s.isDirty()).toBe(false);
  });

  it("ignores requests for unknown overlays", () => {
    const s = new TimelineOverlayScheduler();
    s.requestOverlayRedraw("nonexistent", region);
    expect(s.isDirty()).toBe(false);
  });

  it("requestOverlayRedraw with null region is supported", () => {
    const s = new TimelineOverlayScheduler();
    s.register({ id: "cursor", coalesce: true });
    s.requestOverlayRedraw("cursor", null);
    const drained = s.flush();
    expect(drained[0]!.region).toBeNull();
  });
});
