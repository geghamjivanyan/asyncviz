/**
 * Local sort + filter state for the live task table.
 *
 * The state is component-local on purpose: it's UI-only and doesn't
 * need to survive a route change or hydration. Selection is *not*
 * stored here — it lives in the canonical runtime store
 * (``selectedTaskId``) so the inspector and timeline see the same
 * selection.
 */

import { useCallback, useState } from "react";
import {
  DEFAULT_FILTERS,
  DEFAULT_SORT,
  type TaskFilterState,
  type TaskSortState,
} from "@/dashboard/tasks/models/filters";
import type { TaskColumnId } from "@/dashboard/tasks/models/columns";

export interface TaskTableStateValue {
  sort: TaskSortState;
  filters: TaskFilterState;
  setSort: (sort: TaskSortState) => void;
  toggleSort: (columnId: TaskColumnId) => void;
  setFilters: (next: Partial<TaskFilterState>) => void;
  resetFilters: () => void;
}

export function useTaskTableState(initial?: {
  sort?: TaskSortState;
  filters?: TaskFilterState;
}): TaskTableStateValue {
  const [sort, setSortState] = useState<TaskSortState>(initial?.sort ?? DEFAULT_SORT);
  const [filters, setFiltersState] = useState<TaskFilterState>(initial?.filters ?? DEFAULT_FILTERS);

  const setSort = useCallback((next: TaskSortState) => {
    setSortState(next);
  }, []);

  const toggleSort = useCallback((columnId: TaskColumnId) => {
    setSortState((prev) => {
      if (prev.columnId === columnId) {
        return { columnId, direction: prev.direction === "asc" ? "desc" : "asc" };
      }
      return { columnId, direction: "asc" };
    });
  }, []);

  const setFilters = useCallback((next: Partial<TaskFilterState>) => {
    setFiltersState((prev) => ({ ...prev, ...next }));
  }, []);

  const resetFilters = useCallback(() => {
    setFiltersState(DEFAULT_FILTERS);
  }, []);

  return { sort, filters, setSort, toggleSort, setFilters, resetFilters };
}
