import { describe, expect, it, vi } from "vitest";
import { TimelineZoomController } from "@/dashboard/timeline/zoom/TimelineZoomController";
import { TimelineZoomMetrics } from "@/dashboard/timeline/zoom/TimelineZoomMetrics";
import { timeAnchor, xAnchor } from "@/dashboard/timeline/zoom/TimelineZoomAnchoring";
import { buildEngine } from "@/dashboard/timeline/zoom/__fixtures__/makeZoomFixtures";

function setup() {
  const engine = buildEngine();
  const metrics = new TimelineZoomMetrics();
  const controller = new TimelineZoomController({ engine, metrics });
  return { engine, metrics, controller };
}

describe("TimelineZoomController", () => {
  it("zoomIn shrinks the visible duration around the cursor", () => {
    const { engine, controller } = setup();
    controller.setCursorTime(5);
    const before = engine.currentScale().durationSeconds;
    controller.zoomIn();
    expect(engine.currentScale().durationSeconds).toBeLessThan(before);
  });

  it("zoomOut grows the visible duration", () => {
    const { engine, controller } = setup();
    const before = engine.currentScale().durationSeconds;
    controller.zoomOut();
    expect(engine.currentScale().durationSeconds).toBeGreaterThan(before);
  });

  it("zoomBy with factor 1 is a noop", () => {
    const { engine, controller, metrics } = setup();
    const before = engine.currentScale().key;
    controller.zoomBy(1, timeAnchor(5));
    expect(engine.currentScale().key).toBe(before);
    expect(metrics.snapshot().noopsSuppressed).toBe(1);
  });

  it("zoomBy preserves the anchor's CSS x", () => {
    const { engine, controller } = setup();
    const xBefore = engine.currentScale().timeToX(5);
    controller.zoomBy(0.5, timeAnchor(5));
    const xAfter = engine.currentScale().timeToX(5);
    expect(xAfter).toBeCloseTo(xBefore, 3);
  });

  it("zoomBy respects min/max constraints", () => {
    const engine = buildEngine({ minDurationSeconds: 5, maxDurationSeconds: 20 });
    const metrics = new TimelineZoomMetrics();
    const controller = new TimelineZoomController({ engine, metrics });
    // Drive the duration to 5s (min) before testing
    controller.zoomBy(0.5);
    expect(engine.currentScale().durationSeconds).toBeCloseTo(5);
    const beforeKey = engine.currentScale().key;
    controller.zoomBy(0.1); // try further zoom-in past min
    expect(engine.currentScale().key).toBe(beforeKey);
    expect(metrics.snapshot().constraintHitsMin).toBeGreaterThan(0);
  });

  it("zoomToRange fits the engine to the supplied bounds", () => {
    const { engine, controller, metrics } = setup();
    controller.zoomToRange(2, 6, "fit-all");
    expect(engine.currentScale().timeStart).toBe(2);
    expect(engine.currentScale().timeEnd).toBe(6);
    expect(metrics.snapshot().zoomFits).toBe(1);
  });

  it("zoomToRange rejects degenerate ranges", () => {
    const { controller, metrics } = setup();
    controller.zoomToRange(5, 5);
    expect(metrics.snapshot().zoomFits).toBe(0);
    expect(metrics.snapshot().noopsSuppressed).toBe(1);
  });

  it("applyWheelGesture pivots on the supplied anchor", () => {
    const { engine, controller } = setup();
    const xBefore = engine.currentScale().timeToX(2);
    controller.applyWheelGesture({ deltaY: -100, deltaMode: "pixel" }, xAnchor(20));
    const xAfter = engine.currentScale().timeToX(engine.currentScale().xToTime(20));
    expect(xAfter).toBeCloseTo(20, 3);
    expect(xBefore).not.toBe(xAfter);
  });

  it("activatePreset records both preset + fit metrics", () => {
    const { controller, metrics } = setup();
    controller.activatePreset({ kind: "fit-all", startSeconds: 0, endSeconds: 5 });
    const snap = metrics.snapshot();
    expect(snap.presetActivations).toBe(1);
    expect(snap.zoomFits).toBe(1);
    expect(snap.fitsByKind["fit-all"]).toBe(1);
  });

  it("subscribe receives state updates", () => {
    const { controller } = setup();
    const listener = vi.fn();
    controller.subscribe(listener);
    controller.zoomBy(0.5);
    expect(listener).toHaveBeenCalled();
  });

  it("dispose detaches from the engine", () => {
    const { engine, controller } = setup();
    controller.dispose();
    // Engine still works; controller no-ops.
    const before = engine.currentScale().durationSeconds;
    controller.zoomBy(0.5);
    expect(engine.currentScale().durationSeconds).toBe(before);
  });
});
