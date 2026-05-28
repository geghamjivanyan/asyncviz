import { describe, expect, it } from "vitest";
import { TimelineSelectionMetrics } from "@/dashboard/timeline/selection/TimelineSelectionMetrics";

describe("TimelineSelectionMetrics", () => {
  it("counts selection changes by reason", () => {
    const m = new TimelineSelectionMetrics();
    m.recordSelectionChange("pointer");
    m.recordSelectionChange("keyboard");
    m.recordSelectionChange("clear");
    m.recordSelectionChange("programmatic");
    const snap = m.snapshot();
    expect(snap.selectionChanges).toBe(4);
    expect(snap.pointerSelects).toBe(1);
    expect(snap.keyboardSelects).toBe(1);
    expect(snap.clears).toBe(1);
    expect(snap.programmaticSelects).toBe(1);
  });

  it("tracks navigation kinds", () => {
    const m = new TimelineSelectionMetrics();
    m.recordNavigation("next");
    m.recordNavigation("next");
    m.recordNavigation("prev");
    m.recordNavigation("home");
    m.recordNavigation("end");
    const snap = m.snapshot();
    expect(snap.navigateNext).toBe(2);
    expect(snap.navigatePrev).toBe(1);
    expect(snap.navigateHome).toBe(1);
    expect(snap.navigateEnd).toBe(1);
  });

  it("records center + reveal + noop + restore", () => {
    const m = new TimelineSelectionMetrics();
    m.recordCenter();
    m.recordReveal();
    m.recordNoopSuppressed();
    m.recordRestore(true);
    m.recordRestore(false);
    const snap = m.snapshot();
    expect(snap.centerOnSelectionCalls).toBe(1);
    expect(snap.revealCalls).toBe(1);
    expect(snap.noopsSuppressed).toBe(1);
    expect(snap.restoreCalls).toBe(2);
    expect(snap.restoreMisses).toBe(1);
  });

  it("records change latency", () => {
    const m = new TimelineSelectionMetrics();
    m.recordChangeLatency(1);
    m.recordChangeLatency(5);
    const snap = m.snapshot();
    expect(snap.totalChangeLatencyMs).toBe(6);
    expect(snap.maxChangeLatencyMs).toBe(5);
    expect(snap.lastChangeLatencyMs).toBe(5);
  });

  it("reset clears every counter", () => {
    const m = new TimelineSelectionMetrics();
    m.recordSelectionChange("pointer");
    m.recordNavigation("next");
    m.reset();
    const snap = m.snapshot();
    expect(snap.selectionChanges).toBe(0);
    expect(snap.navigateNext).toBe(0);
  });
});
