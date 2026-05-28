/**
 * Filtering + sorting state shapes for the live task table.
 *
 * Both are intentionally minimal and replay-safe — every field has a
 * deterministic default, and reducers consume the state as values
 * rather than mutating it. The structure is wide enough to support
 * advanced filtering later (multi-select states, free-text search,
 * boolean predicates) without re-architecting.
 */

import type { TaskColumnId } from "@/dashboard/tasks/models/columns";
import type { TaskRowStatus } from "@/dashboard/tasks/models/taskRow";

export type SortDirection = "asc" | "desc";

export interface TaskSortState {
  columnId: TaskColumnId;
  direction: SortDirection;
}

export const DEFAULT_SORT: TaskSortState = { columnId: "started", direction: "desc" };

export interface TaskFilterState {
  /** Restrict to specific row statuses. ``null`` means no restriction. */
  statuses: readonly TaskRowStatus[] | null;
  /** Free-form text search across the label / coroutine / task id. */
  search: string;
  /** ``true`` to hide terminal-state rows (completed / cancelled / failed). */
  hideTerminal: boolean;
  /** ``true`` to keep only rows with at least one warning. */
  warningsOnly: boolean;
  /** ``true`` to keep only rows with an open timeline segment. */
  activeOnly: boolean;
}

export const DEFAULT_FILTERS: TaskFilterState = {
  statuses: null,
  search: "",
  hideTerminal: false,
  warningsOnly: false,
  activeOnly: false,
};

/** Pure: ``true`` when the filter state matches every default — used to
 *  cheaply skip the filter pass when the table is wide open. */
export function isDefaultFilterState(filters: TaskFilterState): boolean {
  return (
    filters.statuses === null &&
    filters.search === "" &&
    !filters.hideTerminal &&
    !filters.warningsOnly &&
    !filters.activeOnly
  );
}
