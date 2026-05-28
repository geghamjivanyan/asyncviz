/**
 * Sort + filter pipeline for the live task table.
 *
 * All functions are pure and operate on :type:`TaskRow` arrays. The
 * pipeline is "filter → sort" because filtering shrinks the candidate
 * set before the (potentially) O(n log n) sort step.
 *
 * Sorting is *stable* — when the comparator returns 0 we fall back to
 * the canonical ``createdAt`` / ``taskId`` order. Replays therefore
 * produce the same row order every time.
 */

import { compareRowsByColumn, type TaskColumnId } from "@/dashboard/tasks/models/columns";
import { compareRowsForStableOrder, type TaskRow } from "@/dashboard/tasks/models/taskRow";
import {
  isDefaultFilterState,
  type TaskFilterState,
  type TaskSortState,
} from "@/dashboard/tasks/models/filters";

export function filterRows(rows: readonly TaskRow[], filters: TaskFilterState): TaskRow[] {
  if (isDefaultFilterState(filters)) {
    return rows.slice();
  }
  const needle = filters.search.trim().toLowerCase();
  const statuses = filters.statuses;
  const statusSet = statuses === null ? null : new Set(statuses);
  const out: TaskRow[] = [];
  for (const row of rows) {
    if (statusSet !== null && !statusSet.has(row.status)) continue;
    if (filters.hideTerminal && row.isTerminal) continue;
    if (filters.warningsOnly && row.warnings.count === 0) continue;
    if (filters.activeOnly && !row.timeline.active) continue;
    if (needle !== "") {
      const hay =
        `${row.label} ${row.coroutineName ?? ""} ${row.taskName ?? ""} ${row.taskId}`.toLowerCase();
      if (!hay.includes(needle)) continue;
    }
    out.push(row);
  }
  return out;
}

export function sortRows(rows: readonly TaskRow[], sort: TaskSortState): TaskRow[] {
  const out = rows.slice();
  const factor = sort.direction === "asc" ? 1 : -1;
  out.sort((a, b) => {
    const primary = compareRowsByColumn(a, b, sort.columnId) * factor;
    if (primary !== 0) return primary;
    return compareRowsForStableOrder(a, b);
  });
  return out;
}

export function applyFilterAndSort(
  rows: readonly TaskRow[],
  filters: TaskFilterState,
  sort: TaskSortState,
): TaskRow[] {
  const filtered = filterRows(rows, filters);
  return sortRows(filtered, sort);
}

/** Public helper so callers can use the same comparator outside the pipeline. */
export function comparatorForColumn(
  columnId: TaskColumnId,
  direction: "asc" | "desc",
): (a: TaskRow, b: TaskRow) => number {
  const factor = direction === "asc" ? 1 : -1;
  return (a, b) => {
    const primary = compareRowsByColumn(a, b, columnId) * factor;
    if (primary !== 0) return primary;
    return compareRowsForStableOrder(a, b);
  };
}
