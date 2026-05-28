/**
 * Run the filter + sort pipeline against the projected rows.
 *
 * Combines :func:`useProjectedTaskRows` with a sort/filter state.
 * Pipeline timings feed :class:`TaskTableMetrics` so the diagnostics
 * page can spot regression in derivation cost.
 */

import { useMemo } from "react";
import type { TaskRow } from "@/dashboard/tasks/models/taskRow";
import type { TaskFilterState, TaskSortState } from "@/dashboard/tasks/models/filters";
import { useProjectedTaskRows } from "@/dashboard/tasks/selectors/storeSelectors";
import { applyFilterAndSort } from "@/dashboard/tasks/utils/sortFilter";
import { getTaskTableMetrics } from "@/dashboard/tasks/observability/tableMetrics";

export function useTaskRows(filters: TaskFilterState, sort: TaskSortState): TaskRow[] {
  const projected = useProjectedTaskRows();
  return useMemo(() => {
    const metrics = getTaskTableMetrics();
    const start = typeof performance !== "undefined" ? performance.now() : Date.now();
    const result = applyFilterAndSort(projected, filters, sort);
    const end = typeof performance !== "undefined" ? performance.now() : Date.now();
    metrics.recordPipeline(end - start);
    return result;
  }, [projected, filters, sort]);
}
