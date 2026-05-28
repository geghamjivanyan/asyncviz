/**
 * Unit tests for the canonical row model.
 *
 * Tests cover the pure helpers — status derivation, severity
 * summarization, label formatting, and the row signature used by
 * memoization. Everything here is replay-safe: identical inputs
 * produce identical outputs every time.
 */

import { describe, expect, it } from "vitest";
import {
  WARNING_SEVERITY_WEIGHT,
  buildTaskRow,
  compareRowsForStableOrder,
  deriveRowLabel,
  deriveTaskRowStatus,
  rowSignature,
  shortenTaskId,
  summarizeRowWarnings,
} from "@/dashboard/tasks/models/taskRow";
import type { ActiveWarning, TaskSnapshot } from "@/types/runtime";

function makeTask(overrides: Partial<TaskSnapshot> = {}): TaskSnapshot {
  return {
    task_id: "t1",
    state: "running",
    created_at: 0,
    updated_at: 0,
    asyncio_task_id: null,
    coroutine_name: null,
    task_name: null,
    parent_task_id: null,
    root_task_id: "t1",
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

function makeWarning(overrides: Partial<ActiveWarning> = {}): ActiveWarning {
  return {
    warning_id: "w1",
    warning_key: "stuck",
    warning_type: "stuck_task",
    severity: "warning",
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
    related_task_ids: ["t1"],
    lineage_root_id: null,
    metadata: {},
    runtime_id: "rt-1",
    ...overrides,
  };
}

describe("deriveTaskRowStatus", () => {
  it("maps lifecycle states 1:1 in the default case", () => {
    expect(
      deriveTaskRowStatus({ lifecycleState: "running", isOrphaned: false, isReplay: false }),
    ).toBe("running");
    expect(
      deriveTaskRowStatus({ lifecycleState: "waiting", isOrphaned: false, isReplay: false }),
    ).toBe("waiting");
    expect(
      deriveTaskRowStatus({ lifecycleState: "created", isOrphaned: false, isReplay: false }),
    ).toBe("pending");
  });

  it("returns 'orphaned' when isOrphaned is true regardless of lifecycle", () => {
    expect(
      deriveTaskRowStatus({ lifecycleState: "running", isOrphaned: true, isReplay: false }),
    ).toBe("orphaned");
  });

  it("returns 'replaying' when isReplay is true and not orphaned", () => {
    expect(
      deriveTaskRowStatus({ lifecycleState: "running", isOrphaned: false, isReplay: true }),
    ).toBe("replaying");
  });

  it("prioritises 'orphaned' over 'replaying'", () => {
    expect(
      deriveTaskRowStatus({ lifecycleState: "running", isOrphaned: true, isReplay: true }),
    ).toBe("orphaned");
  });
});

describe("summarizeRowWarnings", () => {
  it("returns zero-state for empty warning lists", () => {
    expect(summarizeRowWarnings([])).toEqual({ count: 0, highestSeverity: null });
  });

  it("picks the highest severity across warnings", () => {
    const ws: ActiveWarning[] = [
      makeWarning({ warning_id: "w1", severity: "warning" }),
      makeWarning({ warning_id: "w2", severity: "critical" }),
      makeWarning({ warning_id: "w3", severity: "info" }),
    ];
    expect(summarizeRowWarnings(ws)).toEqual({ count: 3, highestSeverity: "critical" });
  });

  it("severity weights are strictly increasing", () => {
    expect(WARNING_SEVERITY_WEIGHT.info).toBeLessThan(WARNING_SEVERITY_WEIGHT.warning);
    expect(WARNING_SEVERITY_WEIGHT.warning).toBeLessThan(WARNING_SEVERITY_WEIGHT.error);
    expect(WARNING_SEVERITY_WEIGHT.error).toBeLessThan(WARNING_SEVERITY_WEIGHT.critical);
  });
});

describe("deriveRowLabel + shortenTaskId", () => {
  it("prefers task_name, then coroutine_name, then short id", () => {
    expect(deriveRowLabel(makeTask({ task_name: "Worker", coroutine_name: "fn" }))).toBe("Worker");
    expect(deriveRowLabel(makeTask({ coroutine_name: "fn" }))).toBe("fn");
    expect(deriveRowLabel(makeTask({ task_id: "abcdefghijklmnopqrstuv" }))).toBe("abcdefghijkl");
  });

  it("shortens ids longer than 12 chars", () => {
    expect(shortenTaskId("abcdef")).toBe("abcdef");
    expect(shortenTaskId("abcdefghijklmnop")).toBe("abcdefghijkl");
  });
});

describe("rowSignature", () => {
  it("changes when any visible field changes", () => {
    const a = buildTaskRow({
      task: makeTask(),
      warningsForTask: [],
      activeSegment: null,
      closedSegmentCount: 0,
      isReplay: false,
      parentExists: true,
      recentlyTouched: false,
    });
    const b = buildTaskRow({
      task: makeTask({ state: "waiting" }),
      warningsForTask: [],
      activeSegment: null,
      closedSegmentCount: 0,
      isReplay: false,
      parentExists: true,
      recentlyTouched: false,
    });
    expect(a.signature).not.toEqual(b.signature);
  });

  it("is stable for identical inputs", () => {
    const task = makeTask();
    const a = buildTaskRow({
      task,
      warningsForTask: [],
      activeSegment: null,
      closedSegmentCount: 0,
      isReplay: false,
      parentExists: true,
      recentlyTouched: false,
    });
    const b = buildTaskRow({
      task,
      warningsForTask: [],
      activeSegment: null,
      closedSegmentCount: 0,
      isReplay: false,
      parentExists: true,
      recentlyTouched: false,
    });
    expect(a.signature).toEqual(b.signature);
  });

  it("works directly without going through buildTaskRow", () => {
    const sig = rowSignature({
      rowKey: "t1",
      taskId: "t1",
      lifecycleState: "running",
      status: "running",
      label: "x",
      coroutineName: null,
      taskName: null,
      parentTaskId: null,
      isOrphaned: false,
      rootTaskId: null,
      depth: 0,
      childCount: 0,
      createdAt: 0,
      updatedAt: 0,
      completedAt: null,
      durationSeconds: null,
      isTerminal: false,
      isReplay: false,
      exceptionType: null,
      exceptionMessage: null,
      cancellationOrigin: null,
      warnings: { count: 0, highestSeverity: null },
      timeline: { active: false, closedSegments: 0, activeSegment: null },
      metrics: { recentlyTouched: false },
      tags: {},
    });
    expect(sig).toContain("t1");
    expect(sig).toContain("running");
  });
});

describe("buildTaskRow", () => {
  it("flags orphans when parent_task_id is set but parentExists is false", () => {
    const row = buildTaskRow({
      task: makeTask({ parent_task_id: "missing" }),
      warningsForTask: [],
      activeSegment: null,
      closedSegmentCount: 0,
      isReplay: false,
      parentExists: false,
      recentlyTouched: false,
    });
    expect(row.isOrphaned).toBe(true);
    expect(row.status).toBe("orphaned");
  });

  it("rolls warnings into a summary on the row", () => {
    const row = buildTaskRow({
      task: makeTask(),
      warningsForTask: [
        makeWarning({ severity: "warning" }),
        makeWarning({ warning_id: "w2", severity: "error" }),
      ],
      activeSegment: null,
      closedSegmentCount: 0,
      isReplay: false,
      parentExists: true,
      recentlyTouched: false,
    });
    expect(row.warnings.count).toBe(2);
    expect(row.warnings.highestSeverity).toBe("error");
  });

  it("propagates terminal / replay flags", () => {
    const row = buildTaskRow({
      task: makeTask({ state: "completed", duration_seconds: 2.5 }),
      warningsForTask: [],
      activeSegment: null,
      closedSegmentCount: 3,
      isReplay: true,
      parentExists: true,
      recentlyTouched: false,
    });
    expect(row.isTerminal).toBe(true);
    expect(row.isReplay).toBe(true);
    expect(row.status).toBe("replaying");
    expect(row.timeline.closedSegments).toBe(3);
    expect(row.durationSeconds).toBe(2.5);
  });
});

describe("compareRowsForStableOrder", () => {
  it("orders by createdAt then taskId", () => {
    const a = buildTaskRow({
      task: makeTask({ task_id: "a", created_at: 1 }),
      warningsForTask: [],
      activeSegment: null,
      closedSegmentCount: 0,
      isReplay: false,
      parentExists: true,
      recentlyTouched: false,
    });
    const b = buildTaskRow({
      task: makeTask({ task_id: "b", created_at: 2 }),
      warningsForTask: [],
      activeSegment: null,
      closedSegmentCount: 0,
      isReplay: false,
      parentExists: true,
      recentlyTouched: false,
    });
    expect(compareRowsForStableOrder(a, b)).toBeLessThan(0);
  });

  it("breaks ties by taskId", () => {
    const a = buildTaskRow({
      task: makeTask({ task_id: "a", created_at: 1 }),
      warningsForTask: [],
      activeSegment: null,
      closedSegmentCount: 0,
      isReplay: false,
      parentExists: true,
      recentlyTouched: false,
    });
    const b = buildTaskRow({
      task: makeTask({ task_id: "b", created_at: 1 }),
      warningsForTask: [],
      activeSegment: null,
      closedSegmentCount: 0,
      isReplay: false,
      parentExists: true,
      recentlyTouched: false,
    });
    expect(compareRowsForStableOrder(a, b)).toBeLessThan(0);
  });
});
