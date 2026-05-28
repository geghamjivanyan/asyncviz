/**
 * Pure row-navigation helpers.
 *
 * Every keyboard navigation routes through these helpers so the
 * controller never duplicates index math. The helpers operate on the
 * canonical row list (in deterministic order) and return the
 * resulting row id.
 */

import type { SelectableRow } from "@/dashboard/timeline/selection/models/TimelineSelectionModels";

/** Pure: return the id of the row at ``index``, or ``null`` when
 *  out of range. */
export function rowAt(rows: readonly SelectableRow[], index: number): string | null {
  if (index < 0 || index >= rows.length) return null;
  return rows[index]?.taskId ?? null;
}

/** Pure: locate the row index for a given task id. ``-1`` when the
 *  task isn't present. */
export function indexOfTask(rows: readonly SelectableRow[], taskId: string | null): number {
  if (taskId === null) return -1;
  for (let i = 0; i < rows.length; i += 1) {
    if (rows[i].taskId === taskId) return i;
  }
  return -1;
}

/** Pure: the next-row id after ``currentTaskId``. Wraps to the first
 *  row when ``wrap`` is true; otherwise stays put at the end. */
export function nextTaskId(
  rows: readonly SelectableRow[],
  currentTaskId: string | null,
  options: { wrap?: boolean } = {},
): string | null {
  if (rows.length === 0) return null;
  const wrap = options.wrap ?? false;
  const index = indexOfTask(rows, currentTaskId);
  if (index < 0) return rows[0].taskId;
  if (index + 1 >= rows.length) return wrap ? rows[0].taskId : rows[rows.length - 1].taskId;
  return rows[index + 1].taskId;
}

/** Pure: the previous-row id before ``currentTaskId``. */
export function previousTaskId(
  rows: readonly SelectableRow[],
  currentTaskId: string | null,
  options: { wrap?: boolean } = {},
): string | null {
  if (rows.length === 0) return null;
  const wrap = options.wrap ?? false;
  const index = indexOfTask(rows, currentTaskId);
  if (index < 0) return rows[0].taskId;
  if (index - 1 < 0) return wrap ? rows[rows.length - 1].taskId : rows[0].taskId;
  return rows[index - 1].taskId;
}

/** Pure: the first row's id. */
export function firstTaskId(rows: readonly SelectableRow[]): string | null {
  return rows.length === 0 ? null : rows[0].taskId;
}

/** Pure: the last row's id. */
export function lastTaskId(rows: readonly SelectableRow[]): string | null {
  return rows.length === 0 ? null : rows[rows.length - 1].taskId;
}

/** Pure: ``true`` when the row index sits at the first row. */
export function isAtFirst(rows: readonly SelectableRow[], taskId: string | null): boolean {
  if (rows.length === 0) return true;
  if (taskId === null) return false;
  return rows[0]?.taskId === taskId;
}

/** Pure: ``true`` when the row index sits at the last row. */
export function isAtLast(rows: readonly SelectableRow[], taskId: string | null): boolean {
  if (rows.length === 0) return true;
  if (taskId === null) return false;
  return rows[rows.length - 1]?.taskId === taskId;
}
