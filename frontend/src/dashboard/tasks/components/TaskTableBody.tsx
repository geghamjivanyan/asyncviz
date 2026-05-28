/**
 * Scrollable body container for the task table.
 *
 * Today every row in the windowing window renders — there is no
 * literal virtualization. The architecture is ready for windowing:
 * rows have stable heights, the visible set is computed by
 * :func:`useVirtualization`, and the container is the only scroll
 * region.
 */

import type { CSSProperties } from "react";
import type { TaskRow as TaskRowData } from "@/dashboard/tasks/models/taskRow";
import type { TaskColumnId } from "@/dashboard/tasks/models/columns";
import { TaskRow } from "@/dashboard/tasks/components/TaskRow";
import { EmptyState } from "@/ui/feedback/EmptyState";
import { useVirtualization } from "@/dashboard/tasks/hooks/useVirtualization";

export interface TaskTableBodyProps {
  rows: readonly TaskRowData[];
  visibleColumns: readonly TaskColumnId[];
  selectedTaskId: string | null;
  onSelect: (taskId: string) => void;
  /** Optional override — surfaces a context-specific empty hint. */
  emptyTitle?: string;
  emptyDescription?: string;
  /** Grid template applied as inline style — produced by :class:`TaskTable`. */
  rowStyle?: CSSProperties;
}

export function TaskTableBody({
  rows,
  visibleColumns,
  selectedTaskId,
  onSelect,
  emptyTitle = "No tasks",
  emptyDescription = "Tasks will appear here as the runtime emits lifecycle events.",
  rowStyle,
}: TaskTableBodyProps) {
  const view = useVirtualization(rows);
  if (view.totalRows === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }
  return (
    <div role="rowgroup" data-task-rowgroup="body" className="flex w-full flex-col">
      {view.visibleRows.map((row) => (
        <TaskRow
          key={row.rowKey}
          row={row}
          visibleColumns={visibleColumns}
          selected={row.taskId === selectedTaskId}
          onSelect={onSelect}
          style={rowStyle}
        />
      ))}
    </div>
  );
}
