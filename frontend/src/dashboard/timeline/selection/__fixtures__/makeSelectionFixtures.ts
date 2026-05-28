/**
 * Shared builders for selection tests.
 */

import type { TaskSnapshot } from "@/types/runtime";
import type {
  SelectableRow,
  SelectionReason,
} from "@/dashboard/timeline/selection/models/TimelineSelectionModels";
import type { SelectionStore } from "@/dashboard/timeline/selection/TimelineSelectionStore";

export function makeRows(count: number): SelectableRow[] {
  const rows: SelectableRow[] = [];
  for (let i = 0; i < count; i += 1) {
    rows.push({ rowIndex: i, taskId: `t${i}` });
  }
  return rows;
}

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
    runtime_id: "rt",
    tags: {},
    metadata: {},
    ...overrides,
  };
}

/** Simple in-memory selection store for controller tests. */
export function makeInMemoryStore(initial: string | null = null): SelectionStore & {
  history: { taskId: string | null; reason?: SelectionReason }[];
} {
  let current = initial;
  const listeners = new Set<(taskId: string | null) => void>();
  const history: { taskId: string | null }[] = [];
  return {
    getSelectedTaskId: () => current,
    setSelectedTaskId: (taskId) => {
      if (taskId === current) return;
      current = taskId;
      history.push({ taskId });
      for (const listener of listeners) listener(current);
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    history,
  };
}
