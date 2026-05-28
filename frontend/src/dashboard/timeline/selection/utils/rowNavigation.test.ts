import { describe, expect, it } from "vitest";
import {
  firstTaskId,
  indexOfTask,
  isAtFirst,
  isAtLast,
  lastTaskId,
  nextTaskId,
  previousTaskId,
  rowAt,
} from "@/dashboard/timeline/selection/utils/rowNavigation";
import { makeRows } from "@/dashboard/timeline/selection/__fixtures__/makeSelectionFixtures";

describe("row navigation", () => {
  const rows = makeRows(3);

  it("rowAt returns the task id or null", () => {
    expect(rowAt(rows, 0)).toBe("t0");
    expect(rowAt(rows, 2)).toBe("t2");
    expect(rowAt(rows, 5)).toBeNull();
    expect(rowAt(rows, -1)).toBeNull();
  });

  it("indexOfTask returns the row index", () => {
    expect(indexOfTask(rows, "t1")).toBe(1);
    expect(indexOfTask(rows, "missing")).toBe(-1);
    expect(indexOfTask(rows, null)).toBe(-1);
  });

  it("nextTaskId advances + clamps without wrap", () => {
    expect(nextTaskId(rows, "t0")).toBe("t1");
    expect(nextTaskId(rows, "t2")).toBe("t2");
  });

  it("nextTaskId wraps when wrap=true", () => {
    expect(nextTaskId(rows, "t2", { wrap: true })).toBe("t0");
  });

  it("nextTaskId picks the first row when nothing selected", () => {
    expect(nextTaskId(rows, null)).toBe("t0");
  });

  it("previousTaskId steps back + clamps without wrap", () => {
    expect(previousTaskId(rows, "t1")).toBe("t0");
    expect(previousTaskId(rows, "t0")).toBe("t0");
  });

  it("previousTaskId wraps when wrap=true", () => {
    expect(previousTaskId(rows, "t0", { wrap: true })).toBe("t2");
  });

  it("firstTaskId + lastTaskId resolve the edges", () => {
    expect(firstTaskId(rows)).toBe("t0");
    expect(lastTaskId(rows)).toBe("t2");
    expect(firstTaskId([])).toBeNull();
  });

  it("isAtFirst / isAtLast detect the boundaries", () => {
    expect(isAtFirst(rows, "t0")).toBe(true);
    expect(isAtFirst(rows, "t1")).toBe(false);
    expect(isAtLast(rows, "t2")).toBe(true);
    expect(isAtLast(rows, "t1")).toBe(false);
  });
});
