import { describe, expect, it } from "vitest";
import {
  flatGrouping,
  groupByLineageParent,
  groupByTask,
} from "@/dashboard/timeline/segments/TimelineSegmentGrouping";
import { makeProjectionEntry } from "@/dashboard/timeline/segments/__fixtures__/makeSegment";

const entries = [
  makeProjectionEntry("a1", 0, 0, 1, { taskId: "a", parentTaskId: null }),
  makeProjectionEntry("a2", 0, 2, 3, { taskId: "a", parentTaskId: null }),
  makeProjectionEntry("b1", 1, 0, 2, { taskId: "b", parentTaskId: "a" }),
  makeProjectionEntry("c1", 2, 1, 2, { taskId: "c", parentTaskId: null }),
];

describe("segment grouping", () => {
  it("flatGrouping emits one group per entry", () => {
    const grouping = flatGrouping(entries);
    expect(grouping.flat).toBe(true);
    expect(grouping.groups).toHaveLength(entries.length);
  });

  it("groupByTask folds entries with the same task id", () => {
    const grouping = groupByTask(entries);
    const a = grouping.groups.find((g) => g.groupId === "a");
    expect(a?.entries.map((e) => e.segmentId)).toEqual(["a1", "a2"]);
    expect(grouping.groups.find((g) => g.groupId === "b")?.entries).toHaveLength(1);
    expect(grouping.groups.find((g) => g.groupId === "c")?.entries).toHaveLength(1);
  });

  it("groupByLineageParent collapses children under their parent", () => {
    const grouping = groupByLineageParent(entries);
    const a = grouping.groups.find((g) => g.groupId === "a");
    expect(a?.entries.map((e) => e.segmentId).sort()).toEqual(["a1", "a2", "b1"]);
  });

  it("sets earliestStart / latestEnd / hasActive on each group", () => {
    const grouping = groupByTask([
      makeProjectionEntry("x1", 0, 1, 2, { taskId: "x" }),
      makeProjectionEntry("x2", 0, 5, 8, { taskId: "x", isActive: true }),
    ]);
    const x = grouping.groups[0];
    expect(x.earliestStartSeconds).toBe(1);
    expect(x.latestEndSeconds).toBe(8);
    expect(x.hasActive).toBe(true);
  });
});
