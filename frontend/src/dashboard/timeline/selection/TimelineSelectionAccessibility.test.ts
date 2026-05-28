import { describe, expect, it } from "vitest";
import {
  describeSelectionAction,
  describeSelectionState,
} from "@/dashboard/timeline/selection/TimelineSelectionAccessibility";
import { makeTask } from "@/dashboard/timeline/selection/__fixtures__/makeSelectionFixtures";

const baseState = {
  selectedTaskId: null as string | null,
  selectedRowIndex: -1,
  selectedTask: null,
  rowCount: 3,
  atFirst: false,
  atLast: false,
  lastReason: null,
  generation: 0,
};

describe("selection a11y helpers", () => {
  it("describes the empty selection", () => {
    expect(describeSelectionState({ ...baseState, rowCount: 0 })).toContain("No tasks");
    expect(describeSelectionState(baseState)).toContain("No row selected");
  });

  it("describes a selection with row position", () => {
    const text = describeSelectionState({
      ...baseState,
      selectedTaskId: "t1",
      selectedRowIndex: 1,
      selectedTask: makeTask("t1", { task_name: "Worker" }),
    });
    expect(text).toContain("Worker");
    expect(text).toContain("row 2 of 3");
  });

  it("describes navigation actions", () => {
    expect(describeSelectionAction("select-next")).toContain("down");
    expect(describeSelectionAction("select-previous")).toContain("up");
    expect(describeSelectionAction("select-first")).toContain("first");
    expect(describeSelectionAction("select-last")).toContain("last");
    expect(describeSelectionAction("clear-selection")).toContain("Cleared");
    expect(describeSelectionAction("center-selection")).toContain("Centered");
    expect(describeSelectionAction("reveal-selection")).toContain("Revealed");
  });
});
