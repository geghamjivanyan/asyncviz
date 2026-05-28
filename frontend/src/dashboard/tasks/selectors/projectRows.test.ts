/**
 * Tests for the pure store → row projection.
 *
 * The projection must:
 *
 *   * Build one row per task.
 *   * Annotate warnings + active segments correctly.
 *   * Tag orphaned rows.
 *   * Sort by the canonical stable comparator.
 *   * Be deterministic.
 */

import { describe, expect, it } from "vitest";
import { projectTaskRows } from "@/dashboard/tasks/selectors/projectRows";
import type { ActiveTimelineSegment, ActiveWarning, TaskSnapshot } from "@/types/runtime";

function task(overrides: Partial<TaskSnapshot> & { task_id: string }): TaskSnapshot {
  return {
    state: "running",
    created_at: 0,
    updated_at: 0,
    asyncio_task_id: null,
    coroutine_name: null,
    task_name: null,
    parent_task_id: null,
    root_task_id: overrides.task_id,
    depth: 0,
    ancestor_chain: [],
    child_count: 0,
    completed_at: null,
    duration_seconds: null,
    exception_type: null,
    exception_message: null,
    cancellation_origin: null,
    runtime_id: "rt-1",
    tags: {},
    metadata: {},
    ...overrides,
  };
}

function makeSegment(taskId: string): ActiveTimelineSegment {
  return {
    task_id: taskId,
    segment_id: `${taskId}-1`,
    segment_type: "run",
    sequence_start: 1,
    monotonic_start_ns: 0,
    wall_start: 0,
    state: "running",
    parent_task_id: null,
    coroutine_name: null,
    task_name: null,
  };
}

function makeWarning(taskId: string, severity: ActiveWarning["severity"]): ActiveWarning {
  return {
    warning_id: `w-${taskId}-${severity}`,
    warning_key: "k",
    warning_type: "stuck_task",
    severity,
    message: "stuck",
    detector: "stuck",
    created_sequence: null,
    created_monotonic_ns: 0,
    created_at_wall: 0,
    last_observed_sequence: null,
    last_observed_monotonic_ns: 0,
    last_observed_wall: 0,
    occurrence_count: 1,
    resolved: false,
    resolved_sequence: null,
    resolved_monotonic_ns: null,
    resolved_at_wall: null,
    expired: false,
    related_task_ids: [taskId],
    lineage_root_id: null,
    metadata: {},
    runtime_id: null,
  };
}

describe("projectTaskRows", () => {
  it("returns an empty array when there are no tasks", () => {
    expect(
      projectTaskRows({
        tasksById: {},
        activeWarnings: [],
        activeSegmentsByTaskId: {},
        segmentIdsByTaskId: {},
        isReplay: false,
        metricsTouchedTaskIds: new Set(),
      }),
    ).toHaveLength(0);
  });

  it("projects one row per task, ordered by createdAt then id", () => {
    const rows = projectTaskRows({
      tasksById: {
        z: task({ task_id: "z", created_at: 1 }),
        a: task({ task_id: "a", created_at: 1 }),
        b: task({ task_id: "b", created_at: 0 }),
      },
      activeWarnings: [],
      activeSegmentsByTaskId: {},
      segmentIdsByTaskId: {},
      isReplay: false,
      metricsTouchedTaskIds: new Set(),
    });
    expect(rows.map((r) => r.taskId)).toEqual(["b", "a", "z"]);
  });

  it("annotates rows with warnings + active segments", () => {
    const rows = projectTaskRows({
      tasksById: {
        t1: task({ task_id: "t1" }),
      },
      activeWarnings: [makeWarning("t1", "critical"), makeWarning("t1", "info")],
      activeSegmentsByTaskId: { t1: makeSegment("t1") },
      segmentIdsByTaskId: { t1: ["s1", "s2"] },
      isReplay: false,
      metricsTouchedTaskIds: new Set(),
    });
    expect(rows[0]!.warnings.count).toBe(2);
    expect(rows[0]!.warnings.highestSeverity).toBe("critical");
    expect(rows[0]!.timeline.active).toBe(true);
    expect(rows[0]!.timeline.closedSegments).toBe(2);
  });

  it("flags rows whose parent is missing", () => {
    const rows = projectTaskRows({
      tasksById: {
        child: task({ task_id: "child", parent_task_id: "ghost" }),
      },
      activeWarnings: [],
      activeSegmentsByTaskId: {},
      segmentIdsByTaskId: {},
      isReplay: false,
      metricsTouchedTaskIds: new Set(),
    });
    expect(rows[0]!.isOrphaned).toBe(true);
    expect(rows[0]!.status).toBe("orphaned");
  });

  it("does not flag rows whose parent exists in the map", () => {
    const rows = projectTaskRows({
      tasksById: {
        parent: task({ task_id: "parent" }),
        child: task({ task_id: "child", parent_task_id: "parent" }),
      },
      activeWarnings: [],
      activeSegmentsByTaskId: {},
      segmentIdsByTaskId: {},
      isReplay: false,
      metricsTouchedTaskIds: new Set(),
    });
    const child = rows.find((r) => r.taskId === "child")!;
    expect(child.isOrphaned).toBe(false);
  });

  it("propagates the replay flag to every row", () => {
    const rows = projectTaskRows({
      tasksById: {
        t1: task({ task_id: "t1" }),
      },
      activeWarnings: [],
      activeSegmentsByTaskId: {},
      segmentIdsByTaskId: {},
      isReplay: true,
      metricsTouchedTaskIds: new Set(),
    });
    expect(rows[0]!.isReplay).toBe(true);
    expect(rows[0]!.status).toBe("replaying");
  });

  it("is replay-safe — identical inputs produce identical rows", () => {
    const inputs = {
      tasksById: {
        t1: task({ task_id: "t1" }),
        t2: task({ task_id: "t2", created_at: 5 }),
      },
      activeWarnings: [makeWarning("t1", "warning")],
      activeSegmentsByTaskId: { t2: makeSegment("t2") },
      segmentIdsByTaskId: { t1: ["a"] },
      isReplay: false,
      metricsTouchedTaskIds: new Set<string>(),
    };
    const a = projectTaskRows(inputs);
    const b = projectTaskRows(inputs);
    expect(a.map((r) => r.signature)).toEqual(b.map((r) => r.signature));
  });
});
