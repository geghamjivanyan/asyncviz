import { describe, expect, it } from "vitest";
import { MetricsHeaderMetrics } from "@/dashboard/metrics/observability/headerMetrics";

describe("MetricsHeaderMetrics", () => {
  it("starts at zero", () => {
    const metrics = new MetricsHeaderMetrics();
    const snap = metrics.snapshot();
    expect(snap.projectionRebuilds).toBe(0);
    expect(snap.cardRenders).toBe(0);
    expect(snap.phaseTransitions).toBe(0);
    expect(snap.replayTransitions).toBe(0);
  });

  it("tracks the max selector duration", () => {
    const metrics = new MetricsHeaderMetrics();
    metrics.recordProjection(1.5);
    metrics.recordProjection(3.5);
    metrics.recordProjection(2.0);
    expect(metrics.snapshot().maxSelectorMs).toBeCloseTo(3.5);
    expect(metrics.snapshot().lastSelectorMs).toBeCloseTo(2.0);
  });

  it("ignores invalid durations", () => {
    const metrics = new MetricsHeaderMetrics();
    metrics.recordProjection(Number.NaN);
    metrics.recordProjection(-1);
    expect(metrics.snapshot().maxSelectorMs).toBe(0);
  });

  it("counts transitions + aggregations + samples", () => {
    const metrics = new MetricsHeaderMetrics();
    metrics.recordPhaseTransition();
    metrics.recordPhaseTransition();
    metrics.recordReplayTransition();
    metrics.recordWarningAggregation();
    metrics.recordThroughputSample();
    metrics.recordThroughputSample();
    const snap = metrics.snapshot();
    expect(snap.phaseTransitions).toBe(2);
    expect(snap.replayTransitions).toBe(1);
    expect(snap.warningAggregations).toBe(1);
    expect(snap.throughputSamples).toBe(2);
  });

  it("counts card renders + resets cleanly", () => {
    const metrics = new MetricsHeaderMetrics();
    metrics.recordCardRender();
    metrics.recordCardRender();
    metrics.recordCardRender();
    expect(metrics.snapshot().cardRenders).toBe(3);
    metrics.reset();
    expect(metrics.snapshot().cardRenders).toBe(0);
  });
});
