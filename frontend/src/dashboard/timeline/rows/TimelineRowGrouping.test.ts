import { describe, expect, it } from "vitest";
import { flatGrouping, groupByLineageRoot } from "@/dashboard/timeline/rows/TimelineRowGrouping";
import { normalizeRow } from "@/dashboard/timeline/rows/utils/normalizeRow";

const rows = [
  normalizeRow({ rowIndex: 0, taskId: "a", label: "A", state: "running" }),
  normalizeRow({
    rowIndex: 1,
    taskId: "b",
    label: "B",
    state: "waiting",
    parentTaskId: "a",
  }),
  normalizeRow({
    rowIndex: 2,
    taskId: "c",
    label: "C",
    state: "waiting",
    parentTaskId: "a",
  }),
  normalizeRow({ rowIndex: 3, taskId: "d", label: "D", state: "running" }),
];

describe("row grouping", () => {
  it("flatGrouping produces one group per row", () => {
    const grouping = flatGrouping(rows);
    expect(grouping.flat).toBe(true);
    expect(grouping.groups).toHaveLength(rows.length);
  });

  it("groupByLineageRoot collapses children under their parents", () => {
    const grouping = groupByLineageRoot(rows);
    const a = grouping.groups.find((g) => g.groupId === "a");
    // Group "a" contains the root + both children because root has no parent.
    expect(a?.rows.map((r) => r.taskId)).toEqual(["a", "b", "c"]);
    const d = grouping.groups.find((g) => g.groupId === "d");
    expect(d?.rows.map((r) => r.taskId)).toEqual(["d"]);
  });

  it("preserves rowIndex ordering inside groups", () => {
    const grouping = groupByLineageRoot(rows);
    const sortedIds = grouping.groups.flatMap((g) => g.rows).map((r) => r.rowIndex);
    expect(sortedIds).toEqual([...sortedIds].sort((a, b) => a - b));
  });
});
