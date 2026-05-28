import { describe, expect, it } from "vitest";
import {
  reduceHeartbeat,
  reduceMetricsDelta,
  reduceTaskEvent,
  reduceTimelineDelta,
  reduceWarningDelta,
  reindexTaskState,
  isTaskLifecycleEvent,
} from "@/state/runtime/reducers";
import type {
  ActiveWarning,
  TaskLifecycleEvent,
  TaskLifecycleState,
  TaskSnapshot,
  TimelineSegment,
} from "@/types/runtime";

function makeEvent(overrides: Partial<TaskLifecycleEvent> = {}): TaskLifecycleEvent {
  return {
    event_type: "asyncio.task.created",
    event_id: "evt-1",
    timestamp: 1.0,
    monotonic_ns: 1_000_000,
    runtime_id: "runtime-1",
    task_id: "t1",
    task_name: null,
    coroutine_name: null,
    parent_task_id: null,
    metadata: {},
    ...overrides,
  } as TaskLifecycleEvent;
}

function baseTask(overrides: Partial<TaskSnapshot> = {}): TaskSnapshot {
  return {
    task_id: "t1",
    state: "completed",
    created_at: 0,
    updated_at: 0,
    asyncio_task_id: null,
    coroutine_name: null,
    task_name: null,
    parent_task_id: null,
    root_task_id: "t1",
    depth: 0,
    ancestor_chain: [],
    child_count: 0,
    completed_at: null,
    duration_seconds: null,
    exception_type: null,
    exception_message: null,
    cancellation_origin: null,
    runtime_id: "r1",
    tags: {},
    metadata: {},
    ...overrides,
  };
}

describe("isTaskLifecycleEvent", () => {
  it("accepts known task-event types", () => {
    expect(isTaskLifecycleEvent({ event_type: "asyncio.task.started" })).toBe(true);
  });

  it("rejects unknown event types", () => {
    expect(isTaskLifecycleEvent({ event_type: "wat" })).toBe(false);
  });

  it("rejects null + non-objects", () => {
    expect(isTaskLifecycleEvent(null)).toBe(false);
    expect(isTaskLifecycleEvent("nope")).toBe(false);
  });
});

describe("reduceTaskEvent", () => {
  it("creates a fresh task snapshot when no prior record exists", () => {
    const { next, regressed } = reduceTaskEvent(
      makeEvent({ event_type: "asyncio.task.created" }),
      undefined,
    );
    expect(next.state).toBe("created");
    expect(regressed).toBe(false);
  });

  it("transitions a task from running to completed", () => {
    const existing = baseTask({ state: "running" });
    const { next, regressed } = reduceTaskEvent(
      makeEvent({
        event_type: "asyncio.task.completed",
        timestamp: 5,
      }),
      existing,
    );
    expect(next.state).toBe("completed");
    expect(next.completed_at).toBe(5);
    expect(regressed).toBe(false);
  });

  it("freezes terminal state — late created event does not regress", () => {
    const existing = baseTask({ state: "completed" });
    const { next, regressed } = reduceTaskEvent(
      makeEvent({ event_type: "asyncio.task.created" }),
      existing,
    );
    expect(next.state).toBe("completed");
    expect(regressed).toBe(true);
  });

  it("captures exception_type on failed events", () => {
    const event = makeEvent({
      event_type: "asyncio.task.failed",
    }) as unknown as TaskLifecycleEvent & {
      exception_type: string;
      exception_message: string;
    };
    event.exception_type = "RuntimeError";
    event.exception_message = "boom";
    const { next } = reduceTaskEvent(event, undefined);
    expect(next.exception_type).toBe("RuntimeError");
    expect(next.exception_message).toBe("boom");
  });

  it("captures cancellation_origin on cancelled events", () => {
    const event = makeEvent({
      event_type: "asyncio.task.cancelled",
    }) as unknown as TaskLifecycleEvent & { cancellation_origin: string };
    event.cancellation_origin = "shutdown";
    const { next } = reduceTaskEvent(event, undefined);
    expect(next.cancellation_origin).toBe("shutdown");
  });
});

describe("reindexTaskState", () => {
  const empty: Record<TaskLifecycleState, string[]> = {
    created: [],
    running: [],
    waiting: [],
    completed: [],
    cancelled: [],
    failed: [],
  };

  it("adds a task to the destination bucket", () => {
    const next = reindexTaskState(empty, "t1", undefined, "running");
    expect(next.running).toEqual(["t1"]);
  });

  it("moves a task between buckets on state transition", () => {
    const next = reindexTaskState({ ...empty, running: ["t1"] }, "t1", "running", "completed");
    expect(next.running).toEqual([]);
    expect(next.completed).toEqual(["t1"]);
  });

  it("is idempotent when destination already contains the task", () => {
    const next = reindexTaskState({ ...empty, running: ["t1"] }, "t1", "running", "running");
    expect(next.running).toEqual(["t1"]);
  });
});

describe("reduceHeartbeat", () => {
  it("merges new values onto the prior projection", () => {
    const next = reduceHeartbeat(
      { serverUptimeSeconds: 0, connectedClients: 0 },
      { server_uptime_seconds: 12.5, connected_clients: 3 },
    );
    expect(next).toEqual({ serverUptimeSeconds: 12.5, connectedClients: 3 });
  });

  it("retains prior values when the payload omits them", () => {
    const next = reduceHeartbeat({ serverUptimeSeconds: 5, connectedClients: 2 }, {});
    expect(next).toEqual({ serverUptimeSeconds: 5, connectedClients: 2 });
  });
});

describe("reduceMetricsDelta", () => {
  it("accumulates count deltas", () => {
    const next = reduceMetricsDelta(
      { aggregate: null, deltaCounts: { completed: 1 } },
      {
        event_type: "asyncio.task.completed",
        event_id: "evt",
        sequence: 1,
        last_sequence: 1,
        monotonic_ns: 0,
        wall_seconds: 0,
        changes: { completed: 2, active: -1 },
        duration_added_seconds: null,
        coroutine_name: null,
        terminal_state: null,
      },
    );
    expect(next.deltaCounts).toEqual({ completed: 3, active: -1 });
  });

  it("ignores non-finite values in the changes map", () => {
    const next = reduceMetricsDelta(
      { aggregate: null, deltaCounts: {} },
      {
        event_type: "asyncio.task.completed",
        event_id: "evt",
        sequence: 1,
        last_sequence: 1,
        monotonic_ns: 0,
        wall_seconds: 0,
        changes: { broken: Number.POSITIVE_INFINITY },
        duration_added_seconds: null,
        coroutine_name: null,
        terminal_state: null,
      },
    );
    expect(next.deltaCounts).toEqual({});
  });
});

describe("reduceWarningDelta", () => {
  function makeWarning(overrides: Partial<ActiveWarning> = {}): ActiveWarning {
    return {
      warning_id: "w-1",
      warning_key: "k-1",
      warning_type: "stuck_task",
      severity: "warning",
      detector: "stuck",
      message: "stuck",
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
      related_task_ids: [],
      lineage_root_id: null,
      metadata: {},
      runtime_id: null,
      ...overrides,
    } as ActiveWarning;
  }

  it("activates a new warning and bumps the severity counter", () => {
    const next = reduceWarningDelta(
      {
        warningsById: {},
        activeWarningIds: [],
        resolvedWarningIds: [],
        countsBySeverity: { info: 0, warning: 0, error: 0, critical: 0 },
      },
      {
        change: "activated",
        sequence: 1,
        last_sequence: 1,
        warning: makeWarning(),
      },
    );
    expect(next.activeWarningIds).toEqual(["w-1"]);
    expect(next.countsBySeverity.warning).toBe(1);
  });

  it("moves a warning from active to resolved on 'resolved' change", () => {
    const next = reduceWarningDelta(
      {
        warningsById: { "w-1": makeWarning() },
        activeWarningIds: ["w-1"],
        resolvedWarningIds: [],
        countsBySeverity: { info: 0, warning: 1, error: 0, critical: 0 },
      },
      {
        change: "resolved",
        sequence: 2,
        last_sequence: 2,
        warning: makeWarning(),
      },
    );
    expect(next.activeWarningIds).toEqual([]);
    expect(next.resolvedWarningIds).toEqual(["w-1"]);
    expect(next.countsBySeverity.warning).toBe(0);
  });
});

describe("reduceTimelineDelta", () => {
  function makeSegment(overrides: Partial<TimelineSegment> = {}): TimelineSegment {
    return {
      task_id: "t1",
      segment_id: "s-1",
      segment_type: "run",
      sequence_start: 1,
      sequence_end: 2,
      monotonic_start_ns: 100,
      monotonic_end_ns: 200,
      duration_ns: 100,
      wall_start: 0,
      wall_end: 0.1,
      state: "running",
      parent_task_id: null,
      coroutine_name: null,
      task_name: null,
      metadata: {},
      ...overrides,
    };
  }

  it("records a closed segment under its task", () => {
    const next = reduceTimelineDelta(
      {
        segmentsById: {},
        activeSegmentsByTaskId: {},
        segmentIdsByTaskId: {},
        lastSequence: 0,
      },
      {
        kind: "segment_closed",
        task_id: "t1",
        sequence: 2,
        monotonic_ns: 200,
        wall_seconds: 0.1,
        closed_a_segment: true,
        segment: makeSegment(),
      },
    );
    expect(next.segmentsById["s-1"]).toBeDefined();
    expect(next.segmentIdsByTaskId.t1).toEqual(["s-1"]);
    expect(next.lastSequence).toBe(2);
  });

  it("records the open segment for a task on segment_opened", () => {
    const next = reduceTimelineDelta(
      {
        segmentsById: {},
        activeSegmentsByTaskId: {},
        segmentIdsByTaskId: {},
        lastSequence: 0,
      },
      {
        kind: "segment_opened",
        task_id: "t1",
        sequence: 3,
        monotonic_ns: 300,
        wall_seconds: 0.3,
        closed_a_segment: false,
        open_segment: {
          task_id: "t1",
          segment_id: "active-s-1",
          segment_type: "run",
          sequence_start: 3,
          monotonic_start_ns: 300,
          wall_start: 0.3,
          state: "running",
          parent_task_id: null,
          coroutine_name: null,
          task_name: null,
        },
      },
    );
    expect(next.activeSegmentsByTaskId.t1?.segment_id).toBe("active-s-1");
  });

  it("clears the active segment on span_finalized", () => {
    const next = reduceTimelineDelta(
      {
        segmentsById: {},
        activeSegmentsByTaskId: {
          t1: {
            task_id: "t1",
            segment_id: "active",
            segment_type: "run",
            sequence_start: 1,
            monotonic_start_ns: 0,
            wall_start: 0,
            state: "running",
            parent_task_id: null,
            coroutine_name: null,
            task_name: null,
          },
        },
        segmentIdsByTaskId: {},
        lastSequence: 0,
      },
      {
        kind: "span_finalized",
        task_id: "t1",
        sequence: 5,
        monotonic_ns: 500,
        wall_seconds: 0.5,
        closed_a_segment: false,
        terminal_state: "completed",
      },
    );
    expect(next.activeSegmentsByTaskId.t1).toBeUndefined();
    expect(next.lastSequence).toBe(5);
  });
});
