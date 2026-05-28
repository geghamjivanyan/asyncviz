/**
 * Tests for the pure event-row projection helpers.
 */

import { describe, expect, it } from "vitest";
import {
  buildEventRow,
  categoryForEvent,
  compareEventRowsNewestFirst,
  deriveEventLabel,
  intentForCategory,
  signEventRow,
  summarizeWarnings,
  type EventRow,
} from "@/dashboard/events/models/eventRow";
import type { ActiveWarning, TaskLifecycleEvent } from "@/types/runtime";

function makeEvent(overrides: Partial<TaskLifecycleEvent> = {}): TaskLifecycleEvent {
  return {
    event_type: "asyncio.task.created",
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
  } as TaskLifecycleEvent;
}

function makeWarning(severity: ActiveWarning["severity"], id = "w1"): ActiveWarning {
  return {
    warning_id: id,
    warning_key: "k",
    warning_type: "stuck_task",
    severity,
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
    related_task_ids: ["t1"],
    lineage_root_id: null,
    metadata: {},
    runtime_id: null,
  };
}

describe("categoryForEvent + intentForCategory", () => {
  it("maps every known event_type to a category", () => {
    expect(categoryForEvent(makeEvent({ event_type: "asyncio.task.created" }))).toBe(
      "task.created",
    );
    expect(categoryForEvent(makeEvent({ event_type: "asyncio.task.started" }))).toBe(
      "task.started",
    );
    expect(categoryForEvent(makeEvent({ event_type: "asyncio.task.waiting" }))).toBe(
      "task.waiting",
    );
    expect(categoryForEvent(makeEvent({ event_type: "asyncio.task.resumed" }))).toBe(
      "task.started",
    );
    expect(categoryForEvent(makeEvent({ event_type: "asyncio.task.completed" }))).toBe(
      "task.completed",
    );
    expect(categoryForEvent(makeEvent({ event_type: "asyncio.task.cancelled" }))).toBe(
      "task.cancelled",
    );
    expect(categoryForEvent(makeEvent({ event_type: "asyncio.task.failed" }))).toBe("task.failed");
  });

  it("returns matching intents", () => {
    expect(intentForCategory("task.created")).toBe("accent");
    expect(intentForCategory("task.started")).toBe("success");
    expect(intentForCategory("task.failed")).toBe("danger");
    expect(intentForCategory("task.cancelled")).toBe("warning");
    expect(intentForCategory("task.waiting")).toBe("warning");
  });
});

describe("deriveEventLabel", () => {
  it("prefers task_name, then coroutine, then task_id", () => {
    expect(deriveEventLabel(makeEvent({ task_name: "Worker", coroutine_name: "fn" }))).toBe(
      "Worker",
    );
    expect(deriveEventLabel(makeEvent({ task_name: null, coroutine_name: "fn" }))).toBe("fn");
    expect(deriveEventLabel(makeEvent({ task_id: "abc" }))).toBe("abc");
  });
});

describe("summarizeWarnings", () => {
  it("returns zero-state for an empty list", () => {
    expect(summarizeWarnings([])).toEqual({ count: 0, highestSeverity: null });
  });

  it("picks the highest severity", () => {
    expect(
      summarizeWarnings([
        makeWarning("warning", "a"),
        makeWarning("critical", "b"),
        makeWarning("info", "c"),
      ]),
    ).toEqual({ count: 3, highestSeverity: "critical" });
  });
});

describe("buildEventRow", () => {
  it("builds a row with stable signature", () => {
    const a = buildEventRow({
      event: makeEvent(),
      warningsForTask: [],
      taskKnown: true,
      hasActiveSegment: false,
      source: "live",
    });
    const b = buildEventRow({
      event: makeEvent(),
      warningsForTask: [],
      taskKnown: true,
      hasActiveSegment: false,
      source: "live",
    });
    expect(a.signature).toBe(b.signature);
  });

  it("flags terminal events", () => {
    const row = buildEventRow({
      event: makeEvent({ event_type: "asyncio.task.completed" }),
      warningsForTask: [],
      taskKnown: true,
      hasActiveSegment: false,
      source: "live",
    });
    expect(row.isTerminal).toBe(true);
  });

  it("escalates intent to danger when a critical warning is linked", () => {
    const row = buildEventRow({
      event: makeEvent({ event_type: "asyncio.task.started" }),
      warningsForTask: [makeWarning("critical")],
      taskKnown: true,
      hasActiveSegment: false,
      source: "live",
    });
    expect(row.intent).toBe("danger");
  });

  it("propagates the source flag", () => {
    const row = buildEventRow({
      event: makeEvent(),
      warningsForTask: [],
      taskKnown: false,
      hasActiveSegment: false,
      source: "replay",
    });
    expect(row.source).toBe("replay");
  });

  it("captures exception info on failed rows", () => {
    const row = buildEventRow({
      event: makeEvent({
        event_type: "asyncio.task.failed",
        exception_type: "RuntimeError",
        exception_message: "boom",
      } as Partial<TaskLifecycleEvent>),
      warningsForTask: [],
      taskKnown: true,
      hasActiveSegment: false,
      source: "live",
    });
    expect(row.exceptionType).toBe("RuntimeError");
    expect(row.exceptionMessage).toBe("boom");
  });

  it("captures cancellation origin on cancelled rows", () => {
    const row = buildEventRow({
      event: makeEvent({
        event_type: "asyncio.task.cancelled",
        cancellation_origin: "timeout",
      } as Partial<TaskLifecycleEvent>),
      warningsForTask: [],
      taskKnown: true,
      hasActiveSegment: false,
      source: "live",
    });
    expect(row.cancellationOrigin).toBe("timeout");
  });

  it("flattens metadata into a bounded entry list", () => {
    const row = buildEventRow({
      event: makeEvent({ metadata: { a: 1, b: "two", c: true, d: { nested: 1 } } }),
      warningsForTask: [],
      taskKnown: true,
      hasActiveSegment: false,
      source: "live",
    });
    expect(row.metadata.length).toBeLessThanOrEqual(8);
    const map = new Map(row.metadata.map(([k, v]) => [k, v]));
    expect(map.get("a")).toBe("1");
    expect(map.get("b")).toBe("two");
    expect(map.get("c")).toBe("true");
    expect(map.get("d")).toBe(JSON.stringify({ nested: 1 }));
  });
});

describe("signEventRow", () => {
  it("encodes every visible field", () => {
    const row: Omit<EventRow, "signature"> = {
      rowKey: "evt-1",
      eventId: "evt-1",
      eventType: "asyncio.task.created",
      category: "task.created",
      intent: "accent",
      label: "fn",
      timestamp: 1,
      monotonicNs: 1,
      sequence: null,
      taskId: "t1",
      parentTaskId: null,
      coroutineName: null,
      taskName: null,
      durationSeconds: null,
      exceptionType: null,
      exceptionMessage: null,
      cancellationOrigin: null,
      isTerminal: false,
      source: "live",
      warnings: { count: 0, highestSeverity: null },
      timeline: { hasActiveSegment: false, taskKnown: true },
      metadata: [],
    };
    expect(signEventRow(row)).toContain("evt-1");
    expect(signEventRow(row)).toContain("task.created");
  });
});

describe("compareEventRowsNewestFirst", () => {
  it("orders rows by monotonic_ns descending", () => {
    const make = (id: string, ns: number): EventRow =>
      buildEventRow({
        event: makeEvent({ event_id: id, monotonic_ns: ns }),
        warningsForTask: [],
        taskKnown: false,
        hasActiveSegment: false,
        source: "live",
      });
    const rows = [make("a", 1), make("b", 3), make("c", 2)];
    rows.sort(compareEventRowsNewestFirst);
    expect(rows.map((r) => r.eventId)).toEqual(["b", "c", "a"]);
  });
});
