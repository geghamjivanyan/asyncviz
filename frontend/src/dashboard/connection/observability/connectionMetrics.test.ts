import { describe, expect, it } from "vitest";
import { ConnectionMetrics } from "@/dashboard/connection/observability/connectionMetrics";

describe("ConnectionMetrics", () => {
  it("starts at zero", () => {
    const m = new ConnectionMetrics();
    const snap = m.snapshot();
    expect(snap.projectionRebuilds).toBe(0);
    expect(snap.phaseTransitions).toBe(0);
    expect(snap.indicatorRenders).toBe(0);
  });

  it("counts transitions + appends", () => {
    const m = new ConnectionMetrics();
    m.recordPhaseTransition();
    m.recordPhaseTransition();
    m.recordReplayTransition();
    m.recordReconnectAttempt();
    m.recordHistoryAppend();
    m.recordHydrationStart();
    m.recordHydrationCompletion();
    m.recordHeartbeatStale();
    m.recordHeartbeatOffline();
    const snap = m.snapshot();
    expect(snap.phaseTransitions).toBe(2);
    expect(snap.replayTransitions).toBe(1);
    expect(snap.reconnectAttempts).toBe(1);
    expect(snap.historyAppends).toBe(1);
    expect(snap.hydrationStarts).toBe(1);
    expect(snap.hydrationCompletions).toBe(1);
    expect(snap.heartbeatStaleDetections).toBe(1);
    expect(snap.heartbeatOfflineDetections).toBe(1);
  });

  it("tracks selector durations", () => {
    const m = new ConnectionMetrics();
    m.recordProjection(0.5);
    m.recordProjection(2.0);
    m.recordProjection(1.0);
    expect(m.snapshot().maxSelectorMs).toBeCloseTo(2);
    expect(m.snapshot().lastSelectorMs).toBeCloseTo(1);
  });

  it("ignores invalid durations", () => {
    const m = new ConnectionMetrics();
    m.recordProjection(Number.NaN);
    m.recordProjection(-1);
    expect(m.snapshot().maxSelectorMs).toBe(0);
  });

  it("counts indicator + tooltip renders", () => {
    const m = new ConnectionMetrics();
    m.recordIndicatorRender();
    m.recordIndicatorRender();
    m.recordTooltipRender();
    expect(m.snapshot().indicatorRenders).toBe(2);
    expect(m.snapshot().tooltipRenders).toBe(1);
  });

  it("resets every counter", () => {
    const m = new ConnectionMetrics();
    m.recordProjection(1);
    m.recordPhaseTransition();
    m.reset();
    const snap = m.snapshot();
    expect(snap.projectionRebuilds).toBe(0);
    expect(snap.phaseTransitions).toBe(0);
    expect(snap.maxSelectorMs).toBe(0);
  });
});
