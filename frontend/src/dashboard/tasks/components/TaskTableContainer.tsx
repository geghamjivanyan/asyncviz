/**
 * Store-aware wrapper.
 *
 * The container is the only component that reaches into the canonical
 * Zustand store + the table-local sort/filter state. Everything below
 * it (rows, cells, toolbar) is pure data → JSX.
 *
 * Consumers mount this directly. The container also exposes a thin
 * customization surface (visible columns, initial sort/filter) for
 * pages that want to reuse the table with a different default view.
 */

import { useMemo } from "react";
import { DEFAULT_VISIBLE_COLUMNS, type TaskColumnId } from "@/dashboard/tasks/models/columns";
import type { TaskFilterState, TaskSortState } from "@/dashboard/tasks/models/filters";
import { TaskTable } from "@/dashboard/tasks/components/TaskTable";
import { useProjectedTaskRows } from "@/dashboard/tasks/selectors/storeSelectors";
import { useTaskTableState } from "@/dashboard/tasks/hooks/useTaskTableState";
import { useTaskRows } from "@/dashboard/tasks/hooks/useTaskRows";
import { useTaskSelection } from "@/dashboard/tasks/hooks/useTaskSelection";

export interface TaskTableContainerProps {
  /** Columns to display. Defaults to the full registry order. */
  visibleColumns?: readonly TaskColumnId[];
  initialSort?: TaskSortState;
  initialFilters?: TaskFilterState;
  className?: string;
}

export function TaskTableContainer({
  visibleColumns = DEFAULT_VISIBLE_COLUMNS,
  initialSort,
  initialFilters,
  className,
}: TaskTableContainerProps) {
  const { sort, filters, toggleSort, setFilters, resetFilters } = useTaskTableState({
    sort: initialSort,
    filters: initialFilters,
  });
  const projected = useProjectedTaskRows();
  const rows = useTaskRows(filters, sort);
  const { selectedTaskId, selectTask } = useTaskSelection();
  // Snapshot the visible-columns array so memo/equality stays stable.
  const stableColumns = useMemo(() => visibleColumns, [visibleColumns]);
  return (
    <TaskTable
      rows={rows}
      totalRows={projected.length}
      visibleColumns={stableColumns}
      selectedTaskId={selectedTaskId}
      onSelect={selectTask}
      sort={sort}
      filters={filters}
      onToggleSort={toggleSort}
      onFiltersChange={setFilters}
      onResetFilters={resetFilters}
      className={className}
    />
  );
}
