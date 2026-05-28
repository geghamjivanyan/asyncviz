import { describe, expect, it } from "vitest";
import { TimelinePanMetrics } from "@/dashboard/timeline/pan/TimelinePanMetrics";

describe("TimelinePanMetrics", () => {
  it("counts pans + tracks total delta", () => {
    const m = new TimelinePanMetrics();
    m.recordPan("drag", 1.5);
    m.recordPan("wheel", -0.5);
    m.recordPan("keyboard", 1);
    const snap = m.snapshot();
    expect(snap.pansApplied).toBe(3);
    expect(snap.pansByReason.drag).toBe(1);
    expect(snap.pansByReason.wheel).toBe(1);
    expect(snap.pansByReason.keyboard).toBe(1);
    expect(snap.totalSecondsPanned).toBeCloseTo(2);
    expect(snap.totalAbsSecondsPanned).toBeCloseTo(3);
  });

  it("tracks drag lifecycle", () => {
    const m = new TimelinePanMetrics();
    m.recordDragStart();
    m.recordDragComplete({ durationMs: 800, secondsMoved: 4 });
    m.recordDragStart();
    m.recordDragCancel();
    const snap = m.snapshot();
    expect(snap.dragsStarted).toBe(2);
    expect(snap.dragsCompleted).toBe(1);
    expect(snap.dragsCancelled).toBe(1);
    expect(snap.dragLongestMs).toBe(800);
    expect(snap.dragSecondsTotal).toBe(4);
  });

  it("records wheel + keyboard + center + to-time + edge hits", () => {
    const m = new TimelinePanMetrics();
    m.recordWheel();
    m.recordKeyboard();
    m.recordCenter();
    m.recordPanToTime();
    m.recordConstraintHit("min");
    m.recordConstraintHit("max");
    m.recordNoopSuppressed();
    const snap = m.snapshot();
    expect(snap.wheelGestures).toBe(1);
    expect(snap.keyboardSteps).toBe(1);
    expect(snap.centerCalls).toBe(1);
    expect(snap.panToTimeCalls).toBe(1);
    expect(snap.constraintHitsMin).toBe(1);
    expect(snap.constraintHitsMax).toBe(1);
    expect(snap.noopsSuppressed).toBe(1);
  });

  it("records pan latency stats", () => {
    const m = new TimelinePanMetrics();
    m.recordPanLatency(2);
    m.recordPanLatency(5);
    m.recordPanLatency(1);
    const snap = m.snapshot();
    expect(snap.totalPanLatencyMs).toBe(8);
    expect(snap.maxPanLatencyMs).toBe(5);
    expect(snap.lastPanLatencyMs).toBe(1);
  });

  it("reset clears every counter", () => {
    const m = new TimelinePanMetrics();
    m.recordPan("drag", 1);
    m.recordDragStart();
    m.reset();
    const snap = m.snapshot();
    expect(snap.pansApplied).toBe(0);
    expect(snap.dragsStarted).toBe(0);
  });
});
