import { describe, expect, it } from "vitest";
import {
  decodeSelection,
  encodeSelection,
  selectionPayloadsEqual,
} from "@/dashboard/timeline/selection/TimelineSelectionPersistence";

describe("selection persistence", () => {
  it("encodeSelection wraps the task id", () => {
    expect(encodeSelection("t1").selectedTaskId).toBe("t1");
    expect(encodeSelection(null).selectedTaskId).toBeNull();
  });

  it("decodeSelection accepts strings", () => {
    expect(decodeSelection("t1").selectedTaskId).toBe("t1");
  });

  it("decodeSelection accepts objects + ignores junk", () => {
    expect(decodeSelection({ selectedTaskId: "t2" }).selectedTaskId).toBe("t2");
    expect(decodeSelection({}).selectedTaskId).toBeNull();
    expect(decodeSelection(null).selectedTaskId).toBeNull();
    expect(decodeSelection(undefined).selectedTaskId).toBeNull();
    expect(decodeSelection(123).selectedTaskId).toBeNull();
  });

  it("selectionPayloadsEqual compares by selectedTaskId", () => {
    expect(selectionPayloadsEqual({ selectedTaskId: "a" }, { selectedTaskId: "a" })).toBe(true);
    expect(selectionPayloadsEqual({ selectedTaskId: "a" }, { selectedTaskId: "b" })).toBe(false);
    expect(selectionPayloadsEqual({ selectedTaskId: null }, { selectedTaskId: null })).toBe(true);
  });
});
