/**
 * Tests for the sort + filter pipeline.
 *
 * The pipeline must be deterministic — given the same rows + state,
 * the output order is identical every run. The tests pin down that
 * invariant + the foundational predicates (warnings-only, active-only,
 * search, statuses).
 */

import { describe, expect, it } from "vitest";
import { applyFilterAndSort, filterRows, sortRows } from "@/dashboard/tasks/utils/sortFilter";
import { buildTaskRow, type TaskRow } from "@/dashboard/tasks/models/taskRow";
import { DEFAULT_FILTERS, DEFAULT_SORT } from "@/dashboard/tasks/models/filters";
import type { TaskSnapshot } from "@/types/runtime";

function makeRow(
  overrides: Partial<TaskSnapshot> = {},
  extras?: {
    warnings?: number;
    active?: boolean;
    replay?: boolean;
    orphan?: boolean;
  },
): TaskRow {
  const warnings = extras?.warnings ?? 0;
  return buildTaskRow({
    task: {
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
    },
    warningsForTask: Array.from({ length: warnings }, (_, i) => ({
      warning_id: `w-${i}`,
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
      related_task_ids: [overrides.task_id ?? "t1"],
      lineage_root_id: null,
      metadata: {},
      runtime_id: null,
    })),
    activeSegment: extras?.active
      ? {
          task_id: overrides.task_id ?? "t1",
          segment_id: "s1",
          segment_type: "run",
          sequence_start: 1,
          monotonic_start_ns: 0,
          wall_start: 0,
          state: "running",
          parent_task_id: null,
          coroutine_name: null,
          task_name: null,
        }
      : null,
    closedSegmentCount: 0,
    isReplay: extras?.replay ?? false,
    parentExists: !(extras?.orphan ?? false),
    recentlyTouched: false,
  });
}

describe("filterRows", () => {
  it("returns a copy when filters are default", () => {
    const rows = [makeRow({ task_id: "a" }), makeRow({ task_id: "b" })];
    const out = filterRows(rows, DEFAULT_FILTERS);
    expect(out).toHaveLength(2);
    expect(out).not.toBe(rows);
  });

  it("restricts by status set", () => {
    const rows = [
      makeRow({ task_id: "a", state: "running" }),
      makeRow({ task_id: "b", state: "completed" }),
      makeRow({ task_id: "c", state: "failed" }),
    ];
    const out = filterRows(rows, { ...DEFAULT_FILTERS, statuses: ["running"] });
    expect(out).toHaveLength(1);
    expect(out[0]!.taskId).toBe("a");
  });

  it("hides terminal rows", () => {
    const rows = [
      makeRow({ task_id: "a", state: "running" }),
      makeRow({ task_id: "b", state: "completed" }),
    ];
    const out = filterRows(rows, { ...DEFAULT_FILTERS, hideTerminal: true });
    expect(out.map((r) => r.taskId)).toEqual(["a"]);
  });

  it("filters warnings-only", () => {
    const rows = [
      makeRow({ task_id: "a" }, { warnings: 0 }),
      makeRow({ task_id: "b" }, { warnings: 2 }),
    ];
    const out = filterRows(rows, { ...DEFAULT_FILTERS, warningsOnly: true });
    expect(out.map((r) => r.taskId)).toEqual(["b"]);
  });

  it("filters active-only", () => {
    const rows = [
      makeRow({ task_id: "a" }, { active: false }),
      makeRow({ task_id: "b" }, { active: true }),
    ];
    const out = filterRows(rows, { ...DEFAULT_FILTERS, activeOnly: true });
    expect(out.map((r) => r.taskId)).toEqual(["b"]);
  });

  it("filters by search across id / name / coroutine", () => {
    const rows = [
      makeRow({ task_id: "alpha", coroutine_name: "alpha_fn" }),
      makeRow({ task_id: "beta", coroutine_name: "beta_fn" }),
    ];
    expect(filterRows(rows, { ...DEFAULT_FILTERS, search: "ALPHA" })).toHaveLength(1);
    expect(filterRows(rows, { ...DEFAULT_FILTERS, search: "beta_fn" })).toHaveLength(1);
    expect(filterRows(rows, { ...DEFAULT_FILTERS, search: "nope" })).toHaveLength(0);
  });

  it("hides framework tasks under the default filter", () => {
    const rows = [
      makeRow({ task_id: "user", coroutine_name: "heartbeat" }),
      makeRow({
        task_id: "framework",
        task_name:
          "starlette.middleware.base.BaseHTTPMiddleware.__call__.<locals>.call_next.<locals>.coro",
        coroutine_name: "BaseHTTPMiddleware.__call__.<locals>.call_next.<locals>.coro",
      }),
    ];
    const out = filterRows(rows, DEFAULT_FILTERS);
    expect(out.map((r) => r.taskId)).toEqual(["user"]);
  });

  it("includes framework tasks when hideFramework is off", () => {
    const rows = [
      makeRow({ task_id: "user", coroutine_name: "heartbeat" }),
      makeRow({
        task_id: "framework",
        task_name:
          "starlette.middleware.base.BaseHTTPMiddleware.__call__.<locals>.call_next.<locals>.coro",
      }),
    ];
    const out = filterRows(rows, { ...DEFAULT_FILTERS, hideFramework: false });
    expect(out.map((r) => r.taskId).sort()).toEqual(["framework", "user"]);
  });
});

describe("sortRows", () => {
  it("orders descending by started by default", () => {
    const rows = [
      makeRow({ task_id: "a", created_at: 10 }),
      makeRow({ task_id: "b", created_at: 5 }),
      makeRow({ task_id: "c", created_at: 20 }),
    ];
    const sorted = sortRows(rows, DEFAULT_SORT);
    expect(sorted.map((r) => r.taskId)).toEqual(["c", "a", "b"]);
  });

  it("sorts ascending by duration with null treated as smallest", () => {
    const rows = [
      makeRow({ task_id: "a", duration_seconds: 1 }),
      makeRow({ task_id: "b", duration_seconds: null }),
      makeRow({ task_id: "c", duration_seconds: 3 }),
    ];
    const sorted = sortRows(rows, { columnId: "duration", direction: "asc" });
    expect(sorted.map((r) => r.taskId)).toEqual(["b", "a", "c"]);
  });

  it("is deterministic across runs — same input yields same order", () => {
    const make = () => [
      makeRow({ task_id: "a", created_at: 5 }),
      makeRow({ task_id: "b", created_at: 5 }),
      makeRow({ task_id: "c", created_at: 5 }),
    ];
    const x = sortRows(make(), DEFAULT_SORT).map((r) => r.taskId);
    const y = sortRows(make(), DEFAULT_SORT).map((r) => r.taskId);
    expect(x).toEqual(y);
  });
});

describe("applyFilterAndSort", () => {
  it("filters then sorts in one call", () => {
    const rows = [
      makeRow({ task_id: "a", state: "running", created_at: 1 }),
      makeRow({ task_id: "b", state: "completed", created_at: 2 }),
      makeRow({ task_id: "c", state: "running", created_at: 3 }),
    ];
    const out = applyFilterAndSort(
      rows,
      { ...DEFAULT_FILTERS, hideTerminal: true },
      { columnId: "started", direction: "asc" },
    );
    expect(out.map((r) => r.taskId)).toEqual(["a", "c"]);
  });
});
