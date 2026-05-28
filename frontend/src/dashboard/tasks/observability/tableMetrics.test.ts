import { describe, expect, it } from "vitest";
import { TaskTableMetrics } from "@/dashboard/tasks/observability/tableMetrics";

describe("TaskTableMetrics", () => {
  it("starts at zero", () => {
    const metrics = new TaskTableMetrics();
    const snap = metrics.snapshot();
    expect(snap.projectionRebuilds).toBe(0);
    expect(snap.selectorEvaluations).toBe(0);
    expect(snap.pipelineRuns).toBe(0);
    expect(snap.rowRenders).toBe(0);
    expect(snap.selectionEvents).toBe(0);
    expect(snap.renderStormWarnings).toBe(0);
  });

  it("records projections + tracks max duration", () => {
    const metrics = new TaskTableMetrics();
    metrics.recordProjection(5, 1.5);
    metrics.recordProjection(10, 3.2);
    const snap = metrics.snapshot();
    expect(snap.projectionRebuilds).toBe(2);
    expect(snap.rowsProjectedTotal).toBe(15);
    expect(snap.maxProjectionMs).toBeCloseTo(3.2);
    expect(snap.lastProjectionMs).toBeCloseTo(3.2);
  });

  it("records pipeline runs", () => {
    const metrics = new TaskTableMetrics();
    metrics.recordPipeline(2.5);
    expect(metrics.snapshot().pipelineRuns).toBe(1);
    expect(metrics.snapshot().lastPipelineMs).toBeCloseTo(2.5);
  });

  it("ignores invalid durations without throwing", () => {
    const metrics = new TaskTableMetrics();
    metrics.recordProjection(5, Number.NaN);
    metrics.recordProjection(5, -1);
    expect(metrics.snapshot().maxProjectionMs).toBe(0);
  });

  it("counts selection events", () => {
    const metrics = new TaskTableMetrics();
    metrics.recordSelection();
    metrics.recordSelection();
    expect(metrics.snapshot().selectionEvents).toBe(2);
  });

  it("counts row renders", () => {
    const metrics = new TaskTableMetrics();
    for (let i = 0; i < 5; i += 1) metrics.recordRowRender();
    expect(metrics.snapshot().rowRenders).toBe(5);
  });

  it("resets every counter", () => {
    const metrics = new TaskTableMetrics();
    metrics.recordPipeline(1);
    metrics.recordProjection(2, 2);
    metrics.recordSelection();
    metrics.reset();
    expect(metrics.snapshot().pipelineRuns).toBe(0);
    expect(metrics.snapshot().projectionRebuilds).toBe(0);
    expect(metrics.snapshot().selectionEvents).toBe(0);
  });
});
