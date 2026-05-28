/**
 * Pure projection: store state → :type:`TaskRow` array.
 *
 * The projection is intentionally exposed as a pure function so:
 *
 *   * It can be tested without React / Zustand.
 *   * Memoization is straightforward — callers pass the same input
 *     references, get the same output array reference back.
 *
 * Runtime fields are pulled from the canonical normalized projections
 * the runtime store maintains. The function does *not* look at the
 * store directly — that's the caller hook's responsibility.
 */

import type { ActiveTimelineSegment, ActiveWarning, TaskSnapshot } from "@/types/runtime";
import {
  buildTaskRow,
  compareRowsForStableOrder,
  type TaskRow,
} from "@/dashboard/tasks/models/taskRow";
import { groupWarningsByTask } from "@/dashboard/tasks/utils/grouping";

export interface ProjectionInputs {
  tasksById: Record<string, TaskSnapshot>;
  activeWarnings: readonly ActiveWarning[];
  activeSegmentsByTaskId: Record<string, ActiveTimelineSegment>;
  segmentIdsByTaskId: Record<string, string[]>;
  /** ``true`` when the store has been hydrated but is awaiting deltas. */
  isReplay: boolean;
  /** Per-task metrics-recently-touched flag. */
  metricsTouchedTaskIds: ReadonlySet<string>;
}

export function projectTaskRows(inputs: ProjectionInputs): TaskRow[] {
  const tasks = Object.values(inputs.tasksById);
  if (tasks.length === 0) return [];
  const warningsByTask = groupWarningsByTask(inputs.activeWarnings);
  const parents = new Set(Object.keys(inputs.tasksById));
  const rows: TaskRow[] = tasks.map((task) =>
    buildTaskRow({
      task,
      warningsForTask: warningsByTask[task.task_id] ?? [],
      activeSegment: inputs.activeSegmentsByTaskId[task.task_id] ?? null,
      closedSegmentCount: (inputs.segmentIdsByTaskId[task.task_id] ?? []).length,
      isReplay: inputs.isReplay,
      parentExists: task.parent_task_id !== null ? parents.has(task.parent_task_id) : true,
      recentlyTouched: inputs.metricsTouchedTaskIds.has(task.task_id),
    }),
  );
  rows.sort(compareRowsForStableOrder);
  return rows;
}
