import { describe, expect, it } from "vitest";
import { groupEventRows } from "@/dashboard/events/utils/grouping";
import { buildEventRow, type EventRow } from "@/dashboard/events/models/eventRow";
import type { TaskLifecycleEvent } from "@/types/runtime";

function row(
  overrides: Partial<TaskLifecycleEvent> = {},
  source: "live" | "replay" = "live",
): EventRow {
  return buildEventRow({
    event: {
      event_type: "asyncio.task.started",
      event_id: "evt-1",
      timestamp: 1,
      monotonic_timestamp: 1,
      monotonic_ns: 1_000_000,
      runtime_id: "rt-1",
      source: "test",
      payload_version: 1,
      task_id: "t1",
      parent_task_id: null,
      coroutine_name: null,
      task_name: null,
      metadata: {},
      ...overrides,
    } as TaskLifecycleEvent,
    warningsForTask: [],
    taskKnown: true,
    hasActiveSegment: false,
    source,
  });
}

describe("groupEventRows", () => {
  it("none mode returns one synthetic group", () => {
    const groups = groupEventRows([row(), row({ event_id: "b" })], "none");
    expect(groups).toHaveLength(1);
    expect(groups[0]!.rows).toHaveLength(2);
  });

  it("task mode buckets by task id, preserving order", () => {
    const groups = groupEventRows(
      [
        row({ event_id: "a", task_id: "t1" }),
        row({ event_id: "b", task_id: "t2" }),
        row({ event_id: "c", task_id: "t1" }),
      ],
      "task",
    );
    expect(groups.map((g) => g.groupId)).toEqual(["task:t1", "task:t2"]);
    expect(groups[0]!.rows.map((r) => r.eventId)).toEqual(["a", "c"]);
  });

  it("category mode buckets by event category", () => {
    const groups = groupEventRows(
      [
        row({ event_id: "a", event_type: "asyncio.task.started" }),
        row({ event_id: "b", event_type: "asyncio.task.failed" }),
        row({ event_id: "c", event_type: "asyncio.task.started" }),
      ],
      "category",
    );
    expect(groups.map((g) => g.groupId)).toEqual(["category:task.started", "category:task.failed"]);
  });

  it("replay-batch mode buckets contiguous runs of the same source", () => {
    const groups = groupEventRows(
      [
        row({ event_id: "a" }, "live"),
        row({ event_id: "b" }, "replay"),
        row({ event_id: "c" }, "replay"),
        row({ event_id: "d" }, "live"),
      ],
      "replay-batch",
    );
    expect(groups).toHaveLength(3);
    expect(groups.map((g) => g.rows.length)).toEqual([1, 2, 1]);
  });
});
