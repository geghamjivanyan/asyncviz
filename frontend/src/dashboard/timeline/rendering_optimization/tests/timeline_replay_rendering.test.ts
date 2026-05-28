import { describe, expect, it } from "vitest";
import { TimelineReplayRenderCoordinator } from "../timeline_replay_rendering";
import { isFullRegion } from "../models";

describe("TimelineReplayRenderCoordinator", () => {
  it("starts with no pending tick", () => {
    const c = new TimelineReplayRenderCoordinator();
    expect(c.hasPendingTick()).toBe(false);
    expect(c.emit({ y: 0, height: 100 })).toBeNull();
  });

  it("emits a full region on the first tick", () => {
    const c = new TimelineReplayRenderCoordinator();
    c.recordCursorTick({ sequence: 1, timeSeconds: 1.0 });
    const region = c.emit({ y: 0, height: 100 })!;
    expect(isFullRegion(region)).toBe(true);
    expect(c.stats().keyframesEmitted).toBe(1);
  });

  it("emits an incremental region on subsequent ticks", () => {
    const c = new TimelineReplayRenderCoordinator();
    c.recordCursorTick({ sequence: 1, timeSeconds: 1.0 });
    c.emit({ y: 0, height: 100 });
    c.recordCursorTick({ sequence: 2, timeSeconds: 1.5 });
    const region = c.emit({ y: 0, height: 100 })!;
    expect(isFullRegion(region)).toBe(false);
    expect(region.reason).toBe("replay");
    expect(c.stats().cursorRegionsEmitted).toBe(1);
  });

  it("emits a keyframe when tick.keyframe is true", () => {
    const c = new TimelineReplayRenderCoordinator();
    c.recordCursorTick({ sequence: 1, timeSeconds: 1.0 });
    c.emit({ y: 0, height: 100 });
    c.recordCursorTick({ sequence: 5, timeSeconds: 5.0, keyframe: true });
    const region = c.emit({ y: 0, height: 100 })!;
    expect(isFullRegion(region)).toBe(true);
    expect(c.stats().keyframesEmitted).toBe(2);
  });

  it("coalesces successive ticks within a frame", () => {
    const c = new TimelineReplayRenderCoordinator();
    c.recordCursorTick({ sequence: 1, timeSeconds: 1.0 });
    c.recordCursorTick({ sequence: 2, timeSeconds: 1.5 });
    c.recordCursorTick({ sequence: 3, timeSeconds: 2.0 });
    c.emit({ y: 0, height: 100 });
    expect(c.stats().coalescedTicks).toBe(2);
    expect(c.stats().lastSequence).toBe(3);
  });

  it("resetCursor clears pending state", () => {
    const c = new TimelineReplayRenderCoordinator();
    c.recordCursorTick({ sequence: 1, timeSeconds: 1.0 });
    c.resetCursor();
    expect(c.hasPendingTick()).toBe(false);
    c.recordCursorTick({ sequence: 2, timeSeconds: 2.0 });
    const region = c.emit({ y: 0, height: 100 })!;
    expect(isFullRegion(region)).toBe(true);
  });

  it("deterministic given identical ticks", () => {
    const a = new TimelineReplayRenderCoordinator();
    const b = new TimelineReplayRenderCoordinator();
    a.recordCursorTick({ sequence: 1, timeSeconds: 1.0 });
    a.emit({ y: 0, height: 100 });
    a.recordCursorTick({ sequence: 2, timeSeconds: 2.0 });
    const regionA = a.emit({ y: 0, height: 100 });
    b.recordCursorTick({ sequence: 1, timeSeconds: 1.0 });
    b.emit({ y: 0, height: 100 });
    b.recordCursorTick({ sequence: 2, timeSeconds: 2.0 });
    const regionB = b.emit({ y: 0, height: 100 });
    expect(regionA).toEqual(regionB);
  });
});
