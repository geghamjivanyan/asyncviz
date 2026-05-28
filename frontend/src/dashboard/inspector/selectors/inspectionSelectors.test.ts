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
    expect(inspection.timeline.segmentCount).toBe(1);
    expect(inspection.timeline.activeSegment).not.toBeNull();
    expect(inspection.warnings.count).toBe(1);
    expect(inspection.relationships.childTaskIds).toEqual(["t2", "t3"]);
    expect(inspection.replay.windowHit).toBe(true);
  });
});
