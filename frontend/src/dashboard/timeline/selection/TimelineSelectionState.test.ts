import { describe, expect, it } from "vitest";
import { buildSelectionState } from "@/dashboard/timeline/selection/TimelineSelectionState";
import {
  makeRows,
  makeTask,
} from "@/dashboard/timeline/selection/__fixtures__/makeSelectionFixtures";

describe("buildSelectionState", () => {
  it("captures basic row + task data", () => {
    const rows = makeRows(3);
    const state = buildSelectionState({
      rows,
      selectedTaskId: "t1",
      selectedTask: makeTask("t1"),
    });
    expect(state.selectedTaskId).toBe("t1");
    expect(state.selectedRowIndex).toBe(1);
    expect(state.rowCount).toBe(3);
  });

  it("flags atFirst + atLast at the boundaries", () => {
    const rows = makeRows(2);
    const first = buildSelectionState({ rows, selectedTaskId: "t0" });
    const last = buildSelectionState({ rows, selectedTaskId: "t1" });
    expect(first.atFirst).toBe(true);
    expect(first.atLast).toBe(false);
    expect(last.atFirst).toBe(false);
    expect(last.atLast).toBe(true);
  });

  it("returns selectedRowIndex=-1 for unknown selection", () => {
    const rows = makeRows(2);
    const state = buildSelectionState({ rows, selectedTaskId: "missing" });
    expect(state.selectedRowIndex).toBe(-1);
  });
});
