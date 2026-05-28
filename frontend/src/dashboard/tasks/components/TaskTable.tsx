/**
 * Canonical live task table.
 *
 * Composes the toolbar + header + body inside a single accessible
 * ``role="grid"`` container. The grid template is built once from the
 * visible column set, exposed as a CSS variable on the container,
 * and consumed by each row via inline style. Re-renders of rows
 * don't touch the declaration.
 *
 * The component is consumer-friendly: callers pass already-projected
 * rows + the state objects, the table just renders. The container
 * component :class:`TaskTableContainer` does the store wiring.
 */

import { useMemo } from "react";
import type { CSSProperties } from "react";
import { cn } from "@/lib/cn";
import { COLUMN_LOOKUP } from "@/dashboard/tasks/models/columns";
import type { TaskColumnId } from "@/dashboard/tasks/models/columns";
import type { TaskRow as TaskRowData } from "@/dashboard/tasks/models/taskRow";
import type { TaskFilterState, TaskSortState } from "@/dashboard/tasks/models/filters";
import { TaskTableHeader } from "@/dashboard/tasks/components/TaskTableHeader";
import { TaskTableBody } from "@/dashboard/tasks/components/TaskTableBody";
import { TaskToolbar } from "@/dashboard/tasks/components/TaskToolbar";

export interface TaskTableProps {
  rows: readonly TaskRowData[];
  totalRows: number;
  visibleColumns: readonly TaskColumnId[];
  selectedTaskId: string | null;
  onSelect: (taskId: string) => void;
  sort: TaskSortState;
  filters: TaskFilterState;
  onToggleSort: (columnId: TaskColumnId) => void;
  onFiltersChange: (next: Partial<TaskFilterState>) => void;
  onResetFilters: () => void;
  className?: string;
}

export function TaskTable({
  rows,
  totalRows,
  visibleColumns,
  selectedTaskId,
  onSelect,
  sort,
  filters,
  onToggleSort,
  onFiltersChange,
  onResetFilters,
  className,
}: TaskTableProps) {
  const gridTemplate = useMemo(
    () => visibleColumns.map((id) => COLUMN_LOOKUP[id].width).join(" "),
    [visibleColumns],
  );
  const rowStyle: CSSProperties = { gridTemplateColumns: gridTemplate };
  return (
    <section
      role="grid"
      aria-label="Live task table"
      aria-rowcount={rows.length + 1}
      data-task-table="true"
      className={cn("flex h-full min-h-0 min-w-0 flex-col", className)}
    >
      <TaskToolbar
        filters={filters}
        onFiltersChange={onFiltersChange}
        totalRows={totalRows}
        visibleRows={rows.length}
        onResetFilters={onResetFilters}
      />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-auto">
        <TaskTableHeader
          visibleColumns={visibleColumns}
          sort={sort}
          onToggleSort={onToggleSort}
          rowStyle={rowStyle}
        />
        <TaskTableBody
          rows={rows}
          visibleColumns={visibleColumns}
          selectedTaskId={selectedTaskId}
          onSelect={onSelect}
          rowStyle={rowStyle}
        />
      </div>
    </section>
  );
}
