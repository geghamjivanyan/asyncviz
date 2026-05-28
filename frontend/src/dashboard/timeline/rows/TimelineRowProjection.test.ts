import { describe, expect, it } from "vitest";
import { projectTimelineRows } from "@/dashboard/timeline/rows/TimelineRowProjection";
import { EMPTY_TIMELINE_ROW_PROJECTION } from "@/dashboard/timeline/rows/models/TimelineRowModels";
import { makeTask, makeWarning } from "@/dashboard/timeline/rows/__fixtures__/makeTask";

describe("projectTimelineRows", () => {
  it("returns the empty projection when there are no tasks", () => {
    const projection = projectTimelineRows({ tasksById: {} });
    expect(projection).toBe(EMPTY_TIMELINE_ROW_PROJECTION);
  });

  it("orders rows by created_at then task id", () => {
    const projection = projectTimelineRows({
      tasksById: {
        z: makeTask("z", { created_at: 1 }),
        a: makeTask("a", { created_at: 1 }),
        b: makeTask("b", { created_at: 0 }),
      },
    });
    expect(projection.rows.map((r) => r.taskId)).toEqual(["b", "a", "z"]);
    expect(projection.totalRows).toBe(3);
  });

  it("populates lineage metadata when present on the task", () => {
    const projection = projectTimelineRows({
      tasksById: {
        parent: makeTask("parent", { child_count: 2 }),
        child: makeTask("child", { parent_task_id: "parent", depth: 1 }),
      },
    });
    const child = projection.rows.find((r) => r.taskId === "child")!;
    expect(child.parentTaskId).toBe("parent");
    expect(child.depth).toBe(1);
    const parent = projection.rows.find((r) => r.taskId === "parent")!;
    expect(parent.childCount).toBe(2);
  });

  it("escalates row warning severity by the highest active warning", () => {
    const projection = projectTimelineRows({
      tasksById: { t1: makeTask("t1") },
      activeWarnings: [
        makeWarning("w1", ["t1"], "warning"),
        makeWarning("w2", ["t1"], "critical"),
        makeWarning("w3", ["t1"], "info"),
      ],
    });
    const row = projection.rows[0]!;
    expect(row.warningSeverity).toBe("critical");
    expect(row.warningCount).toBe(3);
  });

  it("skips resolved + expired warnings when computing the tally", () => {
    const projection = projectTimelineRows({
      tasksById: { t1: makeTask("t1") },
      activeWarnings: [
        makeWarning("w1", ["t1"], "critical", { resolved: true }),
        makeWarning("w2", ["t1"], "info", { expired: true }),
        makeWarning("w3", ["t1"], "warning"),
      ],
    });
    const row = projection.rows[0]!;
    expect(row.warningSeverity).toBe("warning");
    expect(row.warningCount).toBe(1);
  });

  it("attaches replay marks when the cursor focuses a task", () => {
    const projection = projectTimelineRows({
      tasksById: { t1: makeTask("t1"), t2: makeTask("t2", { created_at: 1 }) },
      replay: { sequence: 42, focusedTaskId: "t2" },
    });
    expect(projection.rows[0]!.replay).toBeNull();
    expect(projection.rows[1]!.replay).toEqual({ sequence: 42, focused: true });
  });

  it("is replay-safe — identical inputs produce identical row sequences", () => {
    const inputs = {
      tasksById: {
        a: makeTask("a", { created_at: 0 }),
        b: makeTask("b", { created_at: 1 }),
      },
      activeWarnings: [makeWarning("w1", ["a"], "error")],
      sequence: 7,
    };
    const a = projectTimelineRows(inputs);
    const b = projectTimelineRows(inputs);
    expect(a.rows).toEqual(b.rows);
    expect(a.sequence).toBe(b.sequence);
  });

  it("builds lookup tables for O(1) row resolution", () => {
    const projection = projectTimelineRows({
      tasksById: { t1: makeTask("t1"), t2: makeTask("t2", { created_at: 1 }) },
    });
    expect(projection.rowIndexByRowId.get("t1")).toBe(0);
    expect(projection.rowIndexByRowId.get("t2")).toBe(1);
    expect(projection.rowIdByTaskId.get("t1")).toBe("t1");
  });

  it("resolves the label from task_name, then coroutine_name, then taskId", () => {
    const projection = projectTimelineRows({
      tasksById: {
        named: makeTask("named", { task_name: "Worker A", coroutine_name: "fn" }),
        coro: makeTask("coro", { created_at: 1, task_name: null, coroutine_name: "fn2" }),
        bare: makeTask("bare", { created_at: 2, task_name: null, coroutine_name: null }),
      },
    });
    expect(projection.rows[0]!.label).toBe("Worker A");
    expect(projection.rows[1]!.label).toBe("fn2");
    expect(projection.rows[2]!.label).toBe("bare");
  });
});
