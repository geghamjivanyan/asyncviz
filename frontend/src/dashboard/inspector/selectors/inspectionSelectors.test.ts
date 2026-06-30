import { describe, expect, it } from "vitest";
import {
  buildLifecycleSummary,
  buildMetricsSummary,
  buildRelationships,
  buildReplaySummary,
  buildTaskInspection,
  buildTimelineSummary,
  buildWarningsSummary,
} from "@/dashboard/inspector/selectors/inspectionSelectors";
import { EMPTY_TASK_INSPECTION } from "@/dashboard/inspector/models/TaskInspectionModels";
import {
  makeActiveSegment,
  makeSegment,
  makeTask,
  makeWarning,
} from "@/dashboard/inspector/__fixtures__/makeInspectionFixtures";

describe("inspectionSelectors", () => {
  it("buildTaskInspection returns the empty projection when task is null", () => {
    const inspection = buildTaskInspection({ task: null });
    expect(inspection.task).toBeNull();
    expect(inspection.state).toBe(EMPTY_TASK_INSPECTION.state);
  });

  it("buildLifecycleSummary captures state + duration", () => {
    const summary = buildLifecycleSummary(
      makeTask("t1", {
        state: "completed",
        completed_at: 1100,
        duration_seconds: 100,
      }),
      [],
      false,
    );
    expect(summary.state).toBe("completed");
    expect(summary.terminal).toBe(true);
    expect(summary.durationSeconds).toBe(100);
  });

  it("buildTimelineSummary aggregates run + wait totals", () => {
    const segments = [
      makeSegment("s1", "t1", 0, 1_000_000_000), // 1s run
      makeSegment("s2", "t1", 1_000_000_000, 1_500_000_000, {
        segment_type: "wait",
      }),
    ];
    const summary = buildTimelineSummary({ segments, activeSegment: null });
    expect(summary.segmentCount).toBe(2);
    expect(summary.runSegmentCount).toBe(1);
    expect(summary.waitSegmentCount).toBe(1);
    expect(summary.totalRunSeconds).toBeCloseTo(1);
    expect(summary.totalWaitSeconds).toBeCloseTo(0.5);
    expect(summary.firstSegmentStartSeconds).toBe(0);
    expect(summary.lastSegmentEndSeconds).toBeCloseTo(1.5);
  });

  it("buildRelationships pulls lineage from the task snapshot", () => {
    const summary = buildRelationships(
      makeTask("child", {
        parent_task_id: "parent",
        depth: 2,
        root_task_id: "root",
        ancestor_chain: ["parent", "root"],
      }),
      ["sub1", "sub2"],
      4,
    );
    expect(summary.parentTaskId).toBe("parent");
    expect(summary.rootTaskId).toBe("root");
    expect(summary.depth).toBe(2);
    expect(summary.childTaskIds).toEqual(["sub1", "sub2"]);
    expect(summary.siblingCount).toBe(4);
  });

  it("buildWarningsSummary picks the highest severity", () => {
    const summary = buildWarningsSummary([
      makeWarning("w1", ["t1"], "info"),
      makeWarning("w2", ["t1"], "critical"),
      makeWarning("w3", ["t1"], "warning"),
    ]);
    expect(summary.count).toBe(3);
    expect(summary.highestSeverity).toBe("critical");
  });

  it("buildMetricsSummary computes run / wait ratios", () => {
    const timeline = buildTimelineSummary({
      segments: [
        makeSegment("s1", "t1", 0, 1_000_000_000),
        makeSegment("s2", "t1", 1_000_000_000, 1_500_000_000, {
          segment_type: "wait",
        }),
      ],
      activeSegment: null,
    });
    const lifecycle = buildLifecycleSummary(
      makeTask("t1", { duration_seconds: 1.5 }),
      [],
      false,
    );
    const metrics = buildMetricsSummary({ timeline, lifecycle });
    expect(metrics.runRatio).toBeCloseTo(1 / 1.5);
    expect(metrics.waitRatio).toBeCloseTo(0.5 / 1.5);
    expect(metrics.averageSegmentSeconds).toBeCloseTo(0.75);
  });

  it("buildReplaySummary passes through the cursor + window flag", () => {
    const summary = buildReplaySummary({
      oldestRetainedSequence: 1,
      newestRetainedSequence: 5,
      windowHit: true,
      lastSequence: 7,
    });
    expect(summary.windowHit).toBe(true);
    expect(summary.lastSequence).toBe(7);
  });

  it("buildTaskInspection composes every slice", () => {
    const inspection = buildTaskInspection({
      task: makeTask("t1", { task_name: "Worker" }),
      segments: [makeSegment("s1", "t1", 0, 1_000_000_000)],
      activeSegment: makeActiveSegment("t1", 2_000_000_000),
      activeWarnings: [makeWarning("w1", ["t1"], "warning")],
      childTaskIds: ["t2", "t3"],
      siblingCount: 1,
      replay: {
        oldestRetainedSequence: 1,
        newestRetainedSequence: 5,
        windowHit: true,
        lastSequence: 7,
      },
    });
    expect(inspection.task?.task_name).toBe("Worker");
    // Inspector reports the same segments the renderer would draw: one
    // closed run + one open active = 2.
    expect(inspection.timeline.segmentCount).toBe(2);
    expect(inspection.timeline.activeSegment).not.toBeNull();
    expect(inspection.warnings.count).toBe(1);
    expect(inspection.relationships.childTaskIds).toEqual(["t2", "t3"]);
    expect(inspection.replay.windowHit).toBe(true);
  });

  it("Inspector counts the active segment for a running task with no closed segments", () => {
    // Regression: previously a still-running task with only an active
    // segment reported "Segments: 0" / "Duration: -" while the timeline
    // canvas was drawing its live bar. The Inspector should reflect
    // what the renderer shows.
    const task = makeTask("t1", {
      state: "running",
      created_at: 1000,
      updated_at: 1004,
      duration_seconds: null,
    });
    const inspection = buildTaskInspection({
      task,
      segments: [],
      activeSegment: makeActiveSegment("t1", 1_500_000_000, {
        segment_type: "run",
        wall_start: 1001,
      }),
    });
    expect(inspection.timeline.segmentCount).toBe(1);
    expect(inspection.timeline.runSegmentCount).toBe(1);
    // Active segment elapsed = updated_at (1004) − wall_start (1001) = 3s.
    expect(inspection.timeline.totalRunSeconds).toBeCloseTo(3);
    // Live lifecycle duration = updated_at − created_at = 4s.
    expect(inspection.lifecycle.durationSeconds).toBeCloseTo(4);
    expect(inspection.metrics.runRatio).not.toBeNull();
    expect(inspection.metrics.runRatio).toBeGreaterThan(0);
  });

  it("Inspector reports null ratios for a completed task with no segments", () => {
    // Regression: a completed task with a finalized duration but no
    // closed segments (e.g. the task transitioned CREATED → COMPLETED
    // before the timeline engine ever opened a segment) used to report
    // "Run ratio: 0%" / "Wait ratio: 0%" — a fabricated answer. With
    // no segment data the truthful answer is unknown (null → "—").
    const task = makeTask("t1", {
      state: "completed",
      created_at: 1000,
      updated_at: 1000.2127,
      completed_at: 1000.2127,
      duration_seconds: 0.2127,
    });
    const inspection = buildTaskInspection({
      task,
      segments: [],
      activeSegment: null,
    });
    expect(inspection.timeline.segmentCount).toBe(0);
    expect(inspection.lifecycle.durationSeconds).toBeCloseTo(0.2127);
    expect(inspection.metrics.runRatio).toBeNull();
    expect(inspection.metrics.waitRatio).toBeNull();
  });

  it("Inspector still computes a wait-only ratio when only wait segments exist", () => {
    // Counter-regression: the null-ratio fix must not blank ratios for
    // tasks whose segments are real but happen to be all wait (or all
    // run) — the renderer would draw bars and the Inspector must
    // reflect "0% run / 100% wait".
    const task = makeTask("t1", {
      state: "completed",
      created_at: 0,
      updated_at: 1,
      completed_at: 1,
      duration_seconds: 1,
    });
    const inspection = buildTaskInspection({
      task,
      segments: [
        makeSegment("s1", "t1", 0, 1_000_000_000, { segment_type: "wait" }),
      ],
      activeSegment: null,
    });
    expect(inspection.timeline.segmentCount).toBe(1);
    expect(inspection.metrics.runRatio).toBeCloseTo(0);
    expect(inspection.metrics.waitRatio).toBeCloseTo(1);
  });

  it("Inspector accumulates an active wait segment into wait totals", () => {
    const task = makeTask("t1", {
      state: "waiting",
      created_at: 2000,
      updated_at: 2005,
    });
    const inspection = buildTaskInspection({
      task,
      segments: [],
      activeSegment: makeActiveSegment("t1", 0, {
        segment_type: "wait",
        wall_start: 2002,
        state: "waiting",
      }),
    });
    expect(inspection.timeline.segmentCount).toBe(1);
    expect(inspection.timeline.waitSegmentCount).toBe(1);
    expect(inspection.timeline.totalWaitSeconds).toBeCloseTo(3);
    expect(inspection.timeline.totalRunSeconds).toBe(0);
    expect(inspection.metrics.waitRatio).toBeGreaterThan(0);
  });
});
