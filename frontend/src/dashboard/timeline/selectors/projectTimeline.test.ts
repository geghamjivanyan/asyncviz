import { describe, expect, it } from "vitest";
import { projectTimeline } from "@/dashboard/timeline/selectors/projectTimeline";
import type { ActiveTimelineSegment, TaskSnapshot, TimelineSegment } from "@/types/runtime";

function makeTask(taskId: string, createdAt = 0): TaskSnapshot {
  return {
    task_id: taskId,
    state: "running",
    created_at: createdAt,
    updated_at: createdAt,
    asyncio_task_id: null,
    coroutine_name: `${taskId}_fn`,
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

function makeSegment(
  segmentId: string,
  taskId: string,
  startNs: number,
  endNs: number,
  type: TimelineSegment["segment_type"] = "run",
): TimelineSegment {
  return {
    task_id: taskId,
    segment_id: segmentId,
    segment_type: type,
    sequence_start: 1,
    sequence_end: 2,
    monotonic_start_ns: startNs,
    monotonic_end_ns: endNs,
    duration_ns: endNs - startNs,
    wall_start: 0,
    wall_end: 0,
    state: "running",
    parent_task_id: null,
    coroutine_name: null,
    task_name: null,
    metadata: {},
  };
}

function makeActive(taskId: string, startNs: number): ActiveTimelineSegment {
  return {
    task_id: taskId,
    segment_id: `${taskId}-active`,
    segment_type: "run",
    sequence_start: 3,
    monotonic_start_ns: startNs,
    wall_start: 0,
    state: "running",
    parent_task_id: null,
    coroutine_name: null,
    task_name: null,
  };
}

describe("projectTimeline", () => {
  it("returns the empty projection when there are no tasks", () => {
    expect(
      projectTimeline({
        tasksById: {},
        segmentsById: {},
        segmentIdsByTaskId: {},
        activeSegmentsByTaskId: {},
      }).rows,
    ).toHaveLength(0);
  });

  it("orders rows by created_at then task id", () => {
    const projection = projectTimeline({
      tasksById: {
        z: makeTask("z", 1),
        a: makeTask("a", 1),
        b: makeTask("b", 0),
      },
      segmentsById: {},
      segmentIdsByTaskId: {},
      activeSegmentsByTaskId: {},
    });
    expect(projection.rows.map((r) => r.taskId)).toEqual(["b", "a", "z"]);
  });

  it("projects closed segments with seconds coordinates", () => {
    const projection = projectTimeline({
      tasksById: { t1: makeTask("t1") },
      segmentsById: { s1: makeSegment("s1", "t1", 1_000_000_000, 3_000_000_000) },
      segmentIdsByTaskId: { t1: ["s1"] },
      activeSegmentsByTaskId: {},
    });
    expect(projection.segments).toHaveLength(1);
    expect(projection.segments[0]!.startSeconds).toBeCloseTo(1);
    expect(projection.segments[0]!.endSeconds).toBeCloseTo(3);
    expect(projection.segments[0]!.intent).toBe("run");
  });

  it("projects active segments with an open-ended duration", () => {
    const projection = projectTimeline({
      tasksById: { t1: makeTask("t1") },
      segmentsById: {},
      segmentIdsByTaskId: {},
      activeSegmentsByTaskId: { t1: makeActive("t1", 2_000_000_000) },
    });
    expect(projection.segments).toHaveLength(1);
    expect(projection.segments[0]!.isActive).toBe(true);
    expect(projection.segments[0]!.endSeconds).toBeGreaterThan(
      projection.segments[0]!.startSeconds,
    );
  });

  it("tracks min/max time across the projection", () => {
    const projection = projectTimeline({
      tasksById: { t1: makeTask("t1") },
      segmentsById: {
        s1: makeSegment("s1", "t1", 1_000_000_000, 3_000_000_000),
        s2: makeSegment("s2", "t1", 5_000_000_000, 6_000_000_000),
      },
      segmentIdsByTaskId: { t1: ["s1", "s2"] },
      activeSegmentsByTaskId: {},
    });
    expect(projection.minStartSeconds).toBeCloseTo(1);
    expect(projection.maxEndSeconds).toBeCloseTo(6);
  });

  it("is replay-safe — identical inputs produce identical output", () => {
    const inputs = {
      tasksById: { t1: makeTask("t1") },
      segmentsById: { s1: makeSegment("s1", "t1", 0, 1_000_000_000) },
      segmentIdsByTaskId: { t1: ["s1"] },
      activeSegmentsByTaskId: {},
    };
    const a = projectTimeline(inputs);
    const b = projectTimeline(inputs);
    expect(a.rows).toEqual(b.rows);
    expect(a.segments).toEqual(b.segments);
  });
});
