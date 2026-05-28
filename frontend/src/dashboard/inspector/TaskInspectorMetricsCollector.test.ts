import { describe, expect, it } from "vitest";
import { TaskInspectorMetrics } from "@/dashboard/inspector/TaskInspectorMetricsCollector";

describe("TaskInspectorMetrics", () => {
  it("counts projections + tracks latency", () => {
    const m = new TaskInspectorMetrics();
    m.recordProjection(1.5);
    m.recordProjection(0.5);
    const snap = m.snapshot();
    expect(snap.inspectionsBuilt).toBe(2);
    expect(snap.totalProjectionMs).toBeCloseTo(2);
    expect(snap.maxProjectionMs).toBe(1.5);
    expect(snap.lastProjectionMs).toBe(0.5);
  });

  it("counts panel renders by kind", () => {
    const m = new TaskInspectorMetrics();
    m.recordPanelRender("overview");
    m.recordPanelRender("overview");
    m.recordPanelRender("metrics");
    const snap = m.snapshot();
    expect(snap.panelsRendered).toBe(3);
    expect(snap.panelRendersByKind.overview).toBe(2);
    expect(snap.panelRendersByKind.metrics).toBe(1);
  });

  it("counts panel switches + reveal/fit + correlation", () => {
    const m = new TaskInspectorMetrics();
    m.recordPanelSwitch();
    m.recordReveal();
    m.recordFit();
    m.recordWarningCorrelation(3);
    const snap = m.snapshot();
    expect(snap.panelSwitches).toBe(1);
    expect(snap.revealCalls).toBe(1);
    expect(snap.fitCalls).toBe(1);
    expect(snap.warningCorrelations).toBe(3);
  });

  it("reset clears every counter", () => {
    const m = new TaskInspectorMetrics();
    m.recordProjection(1);
    m.recordPanelRender("overview");
    m.recordEmptyState();
    m.recordLoadingState();
    m.recordSelectionRebuild();
    m.reset();
    const snap = m.snapshot();
    expect(snap.inspectionsBuilt).toBe(0);
    expect(snap.emptyStateRenders).toBe(0);
    expect(snap.loadingStateRenders).toBe(0);
    expect(snap.selectionRebuilds).toBe(0);
  });
});
