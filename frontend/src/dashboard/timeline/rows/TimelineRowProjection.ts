/**
 * Pure projection: runtime store → :type:`TimelineRowProjection`.
 *
 * The projection layer translates the canonical task / lineage /
 * warning / replay shapes into a single deterministic structure the
 * row renderer consumes. The function is intentionally:
 *
 *   * pure — no React, no Zustand dependencies,
 *   * deterministic — same input yields identical output (including
 *     ordering),
 *   * cheap — single pass over tasks + a per-task lookup of
 *     auxiliary data,
 *   * replay-safe — every projection captures a ``sequence`` cursor so
 *     downstream consumers can detect divergence.
 */

import type {
  ActiveWarning,
  TaskLifecycleState,
  TaskSnapshot,
  WarningSeverity,
} from "@/types/runtime";
import type {
  TimelineRowReplayMark,
  TimelineRowState,
  TimelineRowWarningSeverity,
} from "@/dashboard/timeline/rendering/TimelineLayer";
import {
  EMPTY_TIMELINE_ROW_PROJECTION,
  type TimelineRowProjection,
  type TimelineRowProjectionEntry,
} from "@/dashboard/timeline/rows/models/TimelineRowModels";

export interface TimelineRowProjectionInputs {
  tasksById: Readonly<Record<string, TaskSnapshot>>;
  activeWarnings?: readonly ActiveWarning[];
  /** Active replay cursor — drives row replay marks. */
  replay?: {
    /** Sequence currently parked on; ``null`` when not replaying. */
    sequence: number | null;
    /** Task id (if any) the replay session is highlighting. */
    focusedTaskId?: string | null;
  } | null;
  /** Sequence cursor of the source data. */
  sequence?: number;
}

const SEVERITY_RANK: Record<TimelineRowWarningSeverity, number> = {
  info: 1,
  warning: 2,
  error: 3,
  critical: 4,
};

function compareTasks(a: TaskSnapshot, b: TaskSnapshot): number {
  if (a.created_at !== b.created_at) return a.created_at - b.created_at;
  return a.task_id.localeCompare(b.task_id);
}

function resolveLabel(task: TaskSnapshot): string {
  return task.task_name?.trim() || task.coroutine_name?.trim() || task.task_id;
}

function normalizeState(state: TaskLifecycleState | undefined): TimelineRowState {
  switch (state) {
    case "created":
    case "running":
    case "waiting":
    case "completed":
    case "cancelled":
    case "failed":
      return state;
    default:
      return "unknown";
  }
}

function normalizeSeverity(value: WarningSeverity): TimelineRowWarningSeverity {
  return value;
}

function escalate(
  current: TimelineRowWarningSeverity | null,
  next: TimelineRowWarningSeverity,
): TimelineRowWarningSeverity {
  if (current === null) return next;
  return SEVERITY_RANK[next] > SEVERITY_RANK[current] ? next : current;
}

interface WarningTally {
  highest: TimelineRowWarningSeverity | null;
  count: number;
}

function buildWarningIndex(
  warnings: readonly ActiveWarning[] | undefined,
): Map<string, WarningTally> {
  const out = new Map<string, WarningTally>();
  if (warnings === undefined) return out;
  for (const warning of warnings) {
    if (warning.resolved || warning.expired) continue;
    const severity = normalizeSeverity(warning.severity);
    const taskIds = warning.related_task_ids;
    if (taskIds.length === 0) continue;
    for (const taskId of taskIds) {
      const existing = out.get(taskId);
      if (existing === undefined) {
        out.set(taskId, { highest: severity, count: 1 });
      } else {
        existing.count += 1;
        existing.highest = escalate(existing.highest, severity);
      }
    }
  }
  return out;
}

function buildReplayMark(
  taskId: string,
  replay: TimelineRowProjectionInputs["replay"],
): TimelineRowReplayMark | null {
  if (!replay) return null;
  const focused = replay.focusedTaskId === taskId;
  // Only emit a mark for the focused row — non-focused rows render
  // their normal state even while replay is active.
  if (!focused) return null;
  return { sequence: replay.sequence, focused };
}

/** Pure: build the canonical row projection from runtime state. */
export function projectTimelineRows(inputs: TimelineRowProjectionInputs): TimelineRowProjection {
  const taskList = Object.values(inputs.tasksById).slice().sort(compareTasks);
  if (taskList.length === 0) return EMPTY_TIMELINE_ROW_PROJECTION;

  const warningIndex = buildWarningIndex(inputs.activeWarnings);
  const rows: TimelineRowProjectionEntry[] = [];
  const rowIndexByRowId = new Map<string, number>();
  const rowIdByTaskId = new Map<string, string>();

  for (let i = 0; i < taskList.length; i += 1) {
    const task = taskList[i];
    const tally = warningIndex.get(task.task_id);
    const rowId = task.task_id;
    const replay = buildReplayMark(task.task_id, inputs.replay ?? null);
    const entry: TimelineRowProjectionEntry = {
      rowIndex: i,
      rowId,
      taskId: task.task_id,
      label: resolveLabel(task),
      coroutineName: task.coroutine_name ?? null,
      state: normalizeState(task.state),
      parentTaskId: task.parent_task_id ?? null,
      depth: Number.isFinite(task.depth) ? task.depth : 0,
      childCount: Number.isFinite(task.child_count) ? task.child_count : 0,
      warningSeverity: tally?.highest ?? null,
      warningCount: tally?.count ?? 0,
      replay,
      createdAtMonotonicNs:
        typeof task.created_at === "number" && Number.isFinite(task.created_at)
          ? Math.round(task.created_at * 1e9)
          : 0,
    };
    rows.push(entry);
    rowIndexByRowId.set(rowId, i);
    rowIdByTaskId.set(task.task_id, rowId);
  }

  return {
    rows,
    rowIndexByRowId,
    rowIdByTaskId,
    sequence: inputs.sequence ?? 0,
    totalRows: rows.length,
  };
}
