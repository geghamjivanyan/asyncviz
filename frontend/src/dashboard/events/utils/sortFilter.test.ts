import { describe, expect, it } from "vitest";
import {
  applyEventFilterAndSort,
  filterEventRows,
  sortEventRows,
} from "@/dashboard/events/utils/sortFilter";
import { buildEventRow, type EventRow } from "@/dashboard/events/models/eventRow";
import { DEFAULT_EVENT_FILTERS, DEFAULT_EVENT_SORT } from "@/dashboard/events/models/filters";
import type { TaskLifecycleEvent } from "@/types/runtime";

function makeRow(
  eventOverrides: Partial<TaskLifecycleEvent> = {},
  options: {
    warnings?: number;
    active?: boolean;
    replay?: boolean;
  } = {},
): EventRow {
  const event: TaskLifecycleEvent = {
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
    ...eventOverrides,
  } as TaskLifecycleEvent;
  return buildEventRow({
    event,
    warningsForTask: Array.from({ length: options.warnings ?? 0 }, (_, i) => ({
      warning_id: `w-${i}`,
      warning_key: "k",
      warning_type: "stuck_task",
      severity: "warning",
      message: "m",
      detector: "d",
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
      related_task_ids: [event.task_id],
      lineage_root_id: null,
      metadata: {},
      runtime_id: null,
    })),
    taskKnown: true,
    hasActiveSegment: options.active ?? false,
    source: options.replay ? "replay" : "live",
  });
}

describe("filterEventRows", () => {
  it("returns a copy when filters are default", () => {
    const rows = [makeRow(), makeRow({ event_id: "b" })];
    const out = filterEventRows(rows, DEFAULT_EVENT_FILTERS);
    expect(out).toHaveLength(2);
    expect(out).not.toBe(rows);
  });

  it("restricts by category", () => {
    const rows = [
      makeRow({ event_id: "a", event_type: "asyncio.task.created" }),
      makeRow({ event_id: "b", event_type: "asyncio.task.failed" }),
    ];
    const out = filterEventRows(rows, {
      ...DEFAULT_EVENT_FILTERS,
      categories: ["task.failed"],
    });
    expect(out.map((r) => r.eventId)).toEqual(["b"]);
  });

  it("keeps only rows with warnings", () => {
    const rows = [makeRow({ event_id: "a" }), makeRow({ event_id: "b" }, { warnings: 1 })];
    expect(
      filterEventRows(rows, { ...DEFAULT_EVENT_FILTERS, warningsOnly: true }).map((r) => r.eventId),
    ).toEqual(["b"]);
  });

  it("keeps only replay rows", () => {
    const rows = [makeRow({ event_id: "a" }), makeRow({ event_id: "b" }, { replay: true })];
    expect(
      filterEventRows(rows, { ...DEFAULT_EVENT_FILTERS, replayOnly: true }).map((r) => r.eventId),
    ).toEqual(["b"]);
  });

  it("keeps only terminal rows", () => {
    const rows = [
      makeRow({ event_id: "a", event_type: "asyncio.task.started" }),
      makeRow({ event_id: "b", event_type: "asyncio.task.completed" }),
    ];
    expect(
      filterEventRows(rows, { ...DEFAULT_EVENT_FILTERS, terminalOnly: true }).map((r) => r.eventId),
    ).toEqual(["b"]);
  });

  it("keeps only rows with an active timeline segment", () => {
    const rows = [makeRow({ event_id: "a" }), makeRow({ event_id: "b" }, { active: true })];
    expect(
      filterEventRows(rows, {
        ...DEFAULT_EVENT_FILTERS,
        activeTimelineOnly: true,
      }).map((r) => r.eventId),
    ).toEqual(["b"]);
  });

  it("restricts by task id", () => {
    const rows = [
      makeRow({ event_id: "a", task_id: "alpha" }),
      makeRow({ event_id: "b", task_id: "beta" }),
    ];
    expect(
      filterEventRows(rows, { ...DEFAULT_EVENT_FILTERS, taskId: "beta" }).map((r) => r.eventId),
    ).toEqual(["b"]);
  });

  it("filters by search across event_id / task / coroutine / label", () => {
    const rows = [
      makeRow({ event_id: "evt-alpha", coroutine_name: "alpha_fn" }),
      makeRow({ event_id: "evt-beta", coroutine_name: "beta_fn" }),
    ];
    expect(
      filterEventRows(rows, { ...DEFAULT_EVENT_FILTERS, search: "BETA" }).map((r) => r.eventId),
    ).toEqual(["evt-beta"]);
  });
});

describe("sortEventRows", () => {
  it("orders newest first by default", () => {
    const rows = [
      makeRow({ event_id: "a", monotonic_ns: 1_000_000 }),
      makeRow({ event_id: "b", monotonic_ns: 3_000_000 }),
      makeRow({ event_id: "c", monotonic_ns: 2_000_000 }),
    ];
    const sorted = sortEventRows(rows, DEFAULT_EVENT_SORT);
    expect(sorted.map((r) => r.eventId)).toEqual(["b", "c", "a"]);
  });

  it("orders oldest first when reversed", () => {
    const rows = [
      makeRow({ event_id: "a", monotonic_ns: 1_000_000 }),
      makeRow({ event_id: "b", monotonic_ns: 3_000_000 }),
      makeRow({ event_id: "c", monotonic_ns: 2_000_000 }),
    ];
    const sorted = sortEventRows(rows, { direction: "oldest" });
    expect(sorted.map((r) => r.eventId)).toEqual(["a", "c", "b"]);
  });

  it("is deterministic across runs", () => {
    const make = () => [
      makeRow({ event_id: "a", monotonic_ns: 1 }),
      makeRow({ event_id: "b", monotonic_ns: 1 }),
      makeRow({ event_id: "c", monotonic_ns: 1 }),
    ];
    expect(sortEventRows(make(), DEFAULT_EVENT_SORT).map((r) => r.eventId)).toEqual(
      sortEventRows(make(), DEFAULT_EVENT_SORT).map((r) => r.eventId),
    );
  });
});

describe("applyEventFilterAndSort", () => {
  it("composes filter + sort", () => {
    const rows = [
      makeRow({ event_id: "a", event_type: "asyncio.task.completed", monotonic_ns: 1 }),
      makeRow({ event_id: "b", event_type: "asyncio.task.started", monotonic_ns: 3 }),
      makeRow({ event_id: "c", event_type: "asyncio.task.completed", monotonic_ns: 2 }),
    ];
    const out = applyEventFilterAndSort(
      rows,
      { ...DEFAULT_EVENT_FILTERS, terminalOnly: true },
      DEFAULT_EVENT_SORT,
    );
    expect(out.map((r) => r.eventId)).toEqual(["c", "a"]);
  });
});
