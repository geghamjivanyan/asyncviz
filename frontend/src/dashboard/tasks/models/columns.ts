/**
 * Column registry for the live task table.
 *
 * Columns are first-class — adding a new column means registering it
 * here, not adding a special-case branch in :class:`TaskRow`. Each
 * column owns its accessor, sort comparator, and accessibility label.
 *
 * The default order is curated for the live runtime view; callers
 * (toolbar / preferences) can override the visible set.
 */

import type { TaskRow } from "@/dashboard/tasks/models/taskRow";

export type TaskColumnId =
  | "status"
  | "label"
  | "coroutine"
  | "duration"
  | "started"
  | "parent"
  | "children"
  | "warnings"
  | "timeline";

export interface TaskColumnDefinition {
  id: TaskColumnId;
  /** Visible header label. */
  label: string;
  /** ``aria-label`` for screen readers; defaults to ``label``. */
  ariaLabel?: string;
  /** ``true`` when the column may be used to sort. */
  sortable: boolean;
  /** Default alignment hint. */
  align: "left" | "right";
  /** Width hint in CSS units (used by the grid template). */
  width: string;
}

export const TASK_COLUMNS: readonly TaskColumnDefinition[] = [
  {
    id: "status",
    label: "Status",
    sortable: true,
    align: "left",
    width: "6.5rem",
  },
  {
    id: "label",
    label: "Task",
    sortable: true,
    align: "left",
    width: "minmax(12rem, 2fr)",
  },
  {
    id: "coroutine",
    label: "Coroutine",
    sortable: true,
    align: "left",
    width: "minmax(8rem, 1fr)",
  },
  {
    id: "duration",
    label: "Duration",
    sortable: true,
    align: "right",
    width: "5.5rem",
  },
  {
    id: "started",
    label: "Started",
    ariaLabel: "Start time",
    sortable: true,
    align: "right",
    width: "6.5rem",
  },
  {
    id: "parent",
    label: "Parent",
    sortable: true,
    align: "left",
    width: "6.5rem",
  },
  {
    id: "children",
    label: "Children",
    ariaLabel: "Child count",
    sortable: true,
    align: "right",
    width: "5.5rem",
  },
  {
    id: "timeline",
    label: "Timeline",
    sortable: false,
    align: "left",
    width: "5.5rem",
  },
  {
    id: "warnings",
    label: "Warnings",
    sortable: true,
    align: "left",
    width: "5.5rem",
  },
];

export const DEFAULT_VISIBLE_COLUMNS: readonly TaskColumnId[] = TASK_COLUMNS.map((c) => c.id);

export const COLUMN_LOOKUP: Record<TaskColumnId, TaskColumnDefinition> = TASK_COLUMNS.reduce(
  (acc, col) => {
    acc[col.id] = col;
    return acc;
  },
  {} as Record<TaskColumnId, TaskColumnDefinition>,
);

/** Pure: comparator used by sortable columns. */
export function compareRowsByColumn(a: TaskRow, b: TaskRow, columnId: TaskColumnId): number {
  switch (columnId) {
    case "status":
      return a.status.localeCompare(b.status);
    case "label":
      return a.label.localeCompare(b.label);
    case "coroutine":
      return (a.coroutineName ?? "").localeCompare(b.coroutineName ?? "");
    case "duration": {
      const ad = a.durationSeconds ?? -1;
      const bd = b.durationSeconds ?? -1;
      return ad - bd;
    }
    case "started":
      return a.createdAt - b.createdAt;
    case "parent":
      return (a.parentTaskId ?? "").localeCompare(b.parentTaskId ?? "");
    case "children":
      return a.childCount - b.childCount;
    case "warnings": {
      const av = a.warnings.count + (a.warnings.highestSeverity !== null ? 0.5 : 0);
      const bv = b.warnings.count + (b.warnings.highestSeverity !== null ? 0.5 : 0);
      return av - bv;
    }
    case "timeline":
      // Timeline column is not sortable; fall back to stable order.
      return 0;
  }
}
