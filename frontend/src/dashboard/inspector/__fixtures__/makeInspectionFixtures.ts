/**
 * Shared builders for inspector tests.
 */

import type {
  ActiveTimelineSegment,
  ActiveWarning,
  TaskSnapshot,
  TimelineSegment,
} from "@/types/runtime";

export function makeTask(
  taskId: string,
  overrides: Partial<TaskSnapshot> = {},
): TaskSnapshot {
  return {
    task_id: taskId,
    state: "running",
    created_at: 1000,
    updated_at: 1002,
    asyncio_task_id: 1,
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
    ...overrides,
  };
}

export function makeSegment(
  segmentId: string,
  taskId: string,
  startNs: number,
  endNs: number,
  overrides: Partial<TimelineSegment> = {},
): TimelineSegment {
  return {
    task_id: taskId,
    segment_id: segmentId,
    segment_type: "run",
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
    ...overrides,
  };
}

export function makeActiveSegment(
  taskId: string,
  startNs: number,
  overrides: Partial<ActiveTimelineSegment> = {},
): ActiveTimelineSegment {
  return {
    task_id: taskId,
    segment_id: `${taskId}-active`,
    segment_type: "run",
    sequence_start: 1,
    monotonic_start_ns: startNs,
    wall_start: 0,
    state: "running",
    parent_task_id: null,
    coroutine_name: null,
    task_name: null,
    ...overrides,
  };
}

export function makeWarning(
  warningId: string,
  taskIds: string[],
  severity: ActiveWarning["severity"] = "warning",
  overrides: Partial<ActiveWarning> = {},
): ActiveWarning {
  return {
    warning_id: warningId,
    warning_key: warningId,
    warning_type: "test.warning",
    severity,
    message: "warn",
    detector: "test",
    created_sequence: 1,
    created_monotonic_ns: 0,
    created_at_wall: 0,
    last_observed_sequence: 1,
    last_observed_monotonic_ns: 0,
    last_observed_wall: 0,
    occurrence_count: 1,
    resolved: false,
    resolved_sequence: null,
    resolved_monotonic_ns: null,
    resolved_at_wall: null,
    expired: false,
    related_task_ids: taskIds,
    lineage_root_id: null,
    metadata: {},
    runtime_id: "rt-1",
    ...overrides,
  };
}
