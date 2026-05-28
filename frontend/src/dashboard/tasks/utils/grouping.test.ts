import { describe, expect, it } from "vitest";
import {
  buildParentExistsSet,
  groupWarningsByTask,
  warningsForTask,
} from "@/dashboard/tasks/utils/grouping";
import type { ActiveWarning, TaskSnapshot } from "@/types/runtime";

function makeWarning(
  id: string,
  relatedTaskIds: string[],
  overrides: Partial<ActiveWarning> = {},
): ActiveWarning {
  return {
    warning_id: id,
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
    related_task_ids: relatedTaskIds,
    lineage_root_id: null,
    metadata: {},
    runtime_id: null,
    ...overrides,
  };
}

describe("groupWarningsByTask", () => {
  it("groups by every related task id", () => {
    const out = groupWarningsByTask([makeWarning("w1", ["a", "b"]), makeWarning("w2", ["b"])]);
    expect(out.a).toHaveLength(1);
    expect(out.b).toHaveLength(2);
  });

  it("returns empty buckets when there are no warnings", () => {
    expect(Object.keys(groupWarningsByTask([])).length).toBe(0);
  });
});

describe("warningsForTask", () => {
  it("returns an empty list when nothing matches", () => {
    expect(warningsForTask({}, "missing")).toHaveLength(0);
  });

  it("returns the matched bucket", () => {
    const warnings = [makeWarning("w1", ["a"])];
    const index = groupWarningsByTask(warnings);
    expect(warningsForTask(index, "a")).toEqual(warnings);
  });
});

describe("buildParentExistsSet", () => {
  it("contains every task id present in the map", () => {
    const tasksById: Record<string, TaskSnapshot> = {
      a: { task_id: "a" } as TaskSnapshot,
      b: { task_id: "b" } as TaskSnapshot,
    };
    const set = buildParentExistsSet(tasksById);
    expect(set.has("a")).toBe(true);
    expect(set.has("b")).toBe(true);
    expect(set.has("c")).toBe(false);
  });
});
