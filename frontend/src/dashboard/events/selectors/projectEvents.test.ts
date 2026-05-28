import { describe, expect, it } from "vitest";
import { projectEventRows } from "@/dashboard/events/selectors/projectEvents";
import type {
  ActiveTimelineSegment,
  ActiveWarning,
  TaskLifecycleEvent,
  TaskSnapshot,
} from "@/types/runtime";

function makeEvent(overrides: Partial<TaskLifecycleEvent> = {}): TaskLifecycleEvent {
  return {
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
  } as TaskLifecycleEvent;
}

function makeTask(taskId: string): TaskSnapshot {
  return {
    task_id: taskId,
    state: "running",
    created_at: 0,
    updated_at: 0,
    asyncio_task_id: null,
    coroutine_name: null,
    task_name: null,
    parent_task_id: null,
    root_task_id: taskId,
    depth: 0,
    ancestor_chain: [],
    child_count: 0,
    completed_at: null,
    duration_seconds: null,
    exception_type: null,
    exception_message: null,
    cancellation_origin: null,
    runtime_id: "rt-1",
    tags: {},
    metadata: {},
  };
}

function makeWarning(taskId: string, severity: ActiveWarning["severity"]): ActiveWarning {
  return {
    warning_id: `w-${taskId}-${severity}`,
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
    related_task_ids: [taskId],
    lineage_root_id: null,
    metadata: {},
    runtime_id: null,
  };
}

function makeSegment(taskId: string): ActiveTimelineSegment {
  return {
    task_id: taskId,
    segment_id: `${taskId}-seg`,
    segment_type: "run",
    sequence_start: 1,
    monotonic_start_ns: 0,
    wall_start: 0,
    state: "running",
    parent_task_id: null,
    coroutine_name: null,
    task_name: null,
  };
}

describe("projectEventRows", () => {
  it("returns an empty array when no events", () => {
    expect(
      projectEventRows({
        events: [],
        tasksById: {},
        activeWarnings: [],
        activeSegmentsByTaskId: {},
      }),
    ).toHaveLength(0);
  });

  it("projects one row per event", () => {
    const rows = projectEventRows({
      events: [makeEvent({ event_id: "a" }), makeEvent({ event_id: "b", monotonic_ns: 2_000_000 })],
      tasksById: { t1: makeTask("t1") },
      activeWarnings: [],
      activeSegmentsByTaskId: {},
    });
    expect(rows).toHaveLength(2);
    expect(rows[0]!.eventId).toBe("a");
    expect(rows[1]!.eventId).toBe("b");
  });

  it("annotates rows with warnings + active segment", () => {
    const rows = projectEventRows({
      events: [makeEvent()],
      tasksById: { t1: makeTask("t1") },
      activeWarnings: [makeWarning("t1", "warning")],
      activeSegmentsByTaskId: { t1: makeSegment("t1") },
    });
    expect(rows[0]!.warnings.count).toBe(1);
    expect(rows[0]!.timeline.hasActiveSegment).toBe(true);
    expect(rows[0]!.timeline.taskKnown).toBe(true);
  });

  it("marks rows from the replay set as replay-source", () => {
    const rows = projectEventRows({
      events: [makeEvent({ event_id: "a" }), makeEvent({ event_id: "b" })],
      tasksById: {},
      activeWarnings: [],
      activeSegmentsByTaskId: {},
      replayEventIds: new Set(["a"]),
    });
    expect(rows[0]!.source).toBe("replay");
    expect(rows[1]!.source).toBe("live");
  });

  it("is replay-safe — identical inputs produce identical signatures", () => {
    const inputs = {
      events: [makeEvent({ event_id: "a" }), makeEvent({ event_id: "b" })],
      tasksById: {},
      activeWarnings: [makeWarning("t1", "info")],
      activeSegmentsByTaskId: {},
    };
    const x = projectEventRows(inputs).map((r) => r.signature);
    const y = projectEventRows(inputs).map((r) => r.signature);
    expect(x).toEqual(y);
  });
});
