import { describe, expect, it, vi } from "vitest";
import { TimelineScaleEngine } from "@/dashboard/timeline/scaling/TimelineScaleEngine";
import { TimelineScaleMetrics } from "@/dashboard/timeline/scaling/TimelineScaleMetrics";

function makeEngine() {
  const metrics = new TimelineScaleMetrics();
  const engine = new TimelineScaleEngine({
    metrics,
    initialTimeStart: 0,
    initialTimeEnd: 10,
    initialViewport: { widthPx: 800, devicePixelRatio: 1 },
  });
  return { engine, metrics };
}

describe("TimelineScaleEngine", () => {
  it("exposes the initial scale", () => {
    const { engine } = makeEngine();
    const scale = engine.currentScale();
    expect(scale.timeStart).toBe(0);
    expect(scale.timeEnd).toBe(10);
    expect(scale.widthPx).toBe(800);
  });

  it("setTimeWindow updates the scale + emits an invalidation", () => {
    const { engine } = makeEngine();
    const listener = vi.fn();
    engine.subscribe(listener);
    engine.setTimeWindow(5, 15);
    expect(engine.currentScale().timeStart).toBe(5);
    expect(engine.currentScale().timeEnd).toBe(15);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener).toHaveBeenCalledWith("scale-window");
  });

  it("zoomAroundTime keeps the anchor stable", () => {
    const { engine } = makeEngine();
    const before = engine.currentScale().timeToX(5);
    engine.zoomAroundTime(5, 0.5);
    const after = engine.currentScale().timeToX(5);
    expect(after).toBeCloseTo(before);
  });

  it("clamps zoom-in at the min duration", () => {
    const engine = new TimelineScaleEngine({
      initialTimeStart: 0,
      initialTimeEnd: 1,
      initialViewport: { widthPx: 800, devicePixelRatio: 1 },
      constraints: { minDurationSeconds: 0.5 },
    });
    engine.zoomAroundTime(0.5, 0.01);
    expect(engine.currentScale().durationSeconds).toBeCloseTo(0.5);
  });

  it("clamps zoom-out at the max duration", () => {
    const engine = new TimelineScaleEngine({
      initialTimeStart: 0,
      initialTimeEnd: 1,
      initialViewport: { widthPx: 800, devicePixelRatio: 1 },
      constraints: { maxDurationSeconds: 100 },
    });
    engine.zoomAroundTime(0.5, 1000);
    expect(engine.currentScale().durationSeconds).toBeCloseTo(100);
  });

  it("pan moves both edges", () => {
    const { engine } = makeEngine();
    engine.pan(5);
    expect(engine.currentScale().timeStart).toBe(5);
    expect(engine.currentScale().timeEnd).toBe(15);
  });

  it("fitToRange snaps the window to the given bounds", () => {
    const { engine } = makeEngine();
    engine.fitToRange(2, 8);
    expect(engine.currentScale().timeStart).toBe(2);
    expect(engine.currentScale().timeEnd).toBe(8);
  });

  it("setViewport re-normalizes the active scale against the new width", () => {
    const { engine } = makeEngine();
    engine.setViewport({ widthPx: 400, devicePixelRatio: 1 });
    expect(engine.currentScale().widthPx).toBe(400);
  });

  it("ticks() caches results across calls", () => {
    const { engine, metrics } = makeEngine();
    engine.ticks();
    engine.ticks();
    const snap = metrics.snapshot();
    expect(snap.cacheMisses).toBe(1);
    expect(snap.cacheHits).toBe(1);
  });

  it("ticks() invalidates on scale changes", () => {
    const { engine, metrics } = makeEngine();
    engine.ticks();
    engine.zoomAroundTime(5, 0.5);
    engine.ticks();
    const snap = metrics.snapshot();
    expect(snap.cacheMisses).toBeGreaterThanOrEqual(2);
  });

  it("setConstraints re-normalizes the scale", () => {
    const { engine } = makeEngine();
    engine.setConstraints({ maxDurationSeconds: 5 });
    expect(engine.currentScale().durationSeconds).toBeLessThanOrEqual(5);
  });

  it("invalidate() emits to listeners without changing scale", () => {
    const { engine } = makeEngine();
    const listener = vi.fn();
    engine.subscribe(listener);
    const before = engine.currentScale();
    engine.invalidate();
    expect(engine.currentScale()).toBe(before);
    expect(listener).toHaveBeenCalledWith("manual");
  });
});
