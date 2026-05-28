/**
 * Foundation for virtualization.
 *
 * The hook returns the indexes of the rows that should be rendered.
 * Today it returns *every* row — the architecture is ready for a
 * windowing implementation (intersection observer / scroll position)
 * without changing call sites. The contract is stable so swapping the
 * implementation is a one-file change.
 *
 * The returned ``rowHeight`` is the stable, configurable height the
 * grid template uses. Stable heights are a prerequisite for fast
 * windowing — they let the implementation skip layout measurement.
 */

import { useMemo } from "react";
import type { TaskRow } from "@/dashboard/tasks/models/taskRow";

export const TASK_ROW_HEIGHT_PX = 28;

export interface VirtualizationWindow {
  startIndex: number;
  endIndex: number;
  rowHeight: number;
  totalRows: number;
  visibleRows: TaskRow[];
}

export function useVirtualization(rows: readonly TaskRow[]): VirtualizationWindow {
  return useMemo(
    () => ({
      startIndex: 0,
      endIndex: rows.length,
      rowHeight: TASK_ROW_HEIGHT_PX,
      totalRows: rows.length,
      visibleRows: rows.slice(),
    }),
    [rows],
  );
}
