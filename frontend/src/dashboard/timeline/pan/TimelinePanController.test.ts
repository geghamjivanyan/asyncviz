import { describe, expect, it, vi } from "vitest";
import { TimelinePanController } from "@/dashboard/timeline/pan/TimelinePanController";
import { TimelinePanMetrics } from "@/dashboard/timeline/pan/TimelinePanMetrics";
import { buildEngine } from "@/dashboard/timeline/pan/__fixtures__/makePanFixtures";

function setup(options: { bounds?: { min: number; max: number } } = {}) {
  const engine = buildEngine();
  const metrics = new TimelinePanMetrics();
  const controller = new TimelinePanController({
    engine,
    metrics,
    bounds: options.bounds
      ? { minTimeSeconds: options.bounds.min, maxTimeSeconds: options.bounds.max }
      : undefined,
  });
  return { engine, metrics, controller };
}

describe("TimelinePanController", () => {
  it("panLeft / panRight shift the viewport by the configured step", () => {
    const { engine, controller } = setup();
    const beforeStart = engine.currentScale().timeStart;
    controller.panRight();
    expect(engine.currentScale().timeStart).toBeGreaterThan(beforeStart);
    controller.panLeft();
    expect(engine.currentScale().timeStart).toBeCloseTo(beforeStart);
  });

  it("shift modifier amplifies the keyboard step", () => {
    const { engine, controller } = setup();
    const beforeStart = engine.currentScale().timeStart;
    controller.panRight({ shift: true });
    const fastDelta = engine.currentScale().timeStart - beforeStart;
    controller.panLeft({ shift: true }); // back
    controller.panRight();
    const slowDelta = engine.currentScale().timeStart - beforeStart;
    expect(Math.abs(fastDelta)).toBeGreaterThan(Math.abs(slowDelta));
  });

  it("panBySeconds with zero delta is a noop", () => {
    const { engine, controller, metrics } = setup();
    const beforeKey = engine.currentScale().key;
    controller.panBySeconds(0);
    expect(engine.currentScale().key).toBe(beforeKey);
    expect(metrics.snapshot().noopsSuppressed).toBe(1);
  });

  it("panBySeconds is bound-clamped + records constraint hits", () => {
    const { engine, controller, metrics } = setup({ bounds: { min: 0, max: 10 } });
    controller.panBySeconds(-5); // try to pan past min
    expect(engine.currentScale().timeStart).toBe(0);
    expect(metrics.snapshot().constraintHitsMin).toBe(1);
  });

  it("panToTime moves the left edge to the target", () => {
    const { engine, controller } = setup();
    controller.panToTime(5);
    expect(engine.currentScale().timeStart).toBe(5);
  });

  it("centerOnTime centers the viewport on the target", () => {
    const { engine, controller } = setup();
    controller.centerOnTime(20);
    expect(engine.currentScale().timeStart + engine.currentScale().durationSeconds / 2).toBeCloseTo(20);
  });

  it("drag lifecycle: beginDrag + updateDrag + endDrag moves the viewport", () => {
    const { engine, controller, metrics } = setup();
    controller.beginDrag({ pointerXCss: 400, pointerTimeSeconds: 5 });
    expect(controller.isDragging()).toBe(true);
    controller.updateDrag({ pointerXCss: 200 }); // pointer moved -200px
    // secondsPerPixel = 10/800 = 0.0125, deltaSeconds = -(-200) * 0.0125 = 2.5
    expect(engine.currentScale().timeStart).toBeCloseTo(2.5);
    controller.endDrag();
    expect(controller.isDragging()).toBe(false);
    const snap = metrics.snapshot();
    expect(snap.dragsStarted).toBe(1);
    expect(snap.dragsCompleted).toBe(1);
  });

  it("cancelDrag aborts without committing further", () => {
    const { controller, metrics } = setup();
    controller.beginDrag({ pointerXCss: 400, pointerTimeSeconds: 5 });
    controller.cancelDrag();
    expect(controller.isDragging()).toBe(false);
    expect(metrics.snapshot().dragsCancelled).toBe(1);
  });

  it("applyWheelGesture pans by the configured delta", () => {
    const { engine, controller, metrics } = setup();
    const before = engine.currentScale().timeStart;
    controller.applyWheelGesture({ deltaXPx: 80 });
    expect(engine.currentScale().timeStart).toBeGreaterThan(before);
    expect(metrics.snapshot().wheelGestures).toBe(1);
  });

  it("subscribe fires on engine changes", () => {
    const { controller } = setup();
    const listener = vi.fn();
    controller.subscribe(listener);
    controller.panRight();
    expect(listener).toHaveBeenCalled();
  });

  it("setBounds applies + refreshes state", () => {
    const { engine, controller } = setup();
    controller.setBounds({ minTimeSeconds: 0, maxTimeSeconds: 5 });
    // Engine is at 0..10 which means the right edge already exceeds the
    // new max. panRight should be a no-op.
    const before = engine.currentScale().timeStart;
    controller.panRight();
    expect(engine.currentScale().timeStart).toBe(before);
  });

  it("dispose detaches the controller", () => {
    const { engine, controller } = setup();
    controller.dispose();
    const before = engine.currentScale().timeStart;
    controller.panRight();
    expect(engine.currentScale().timeStart).toBe(before);
  });
});
