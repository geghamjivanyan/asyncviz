/**
 * Small task / warning builders for row tests. Mirrors the backend
 * wire shape so the projection logic exercises the real path.
 */

import type { ActiveWarning, TaskSnapshot, WarningSeverity } from "@/types/runtime";

export function makeTask(taskId: string, overrides: Partial<TaskSnapshot> = {}): TaskSnapshot {
  return {
    task_id: taskId,
    state: "running",
    created_at: 0,
    updated_at: 0,
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
    ...overrides,
  };
}

export function makeWarning(
  warningId: string,
  taskIds: string[],
  severity: WarningSeverity = "warning",
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
