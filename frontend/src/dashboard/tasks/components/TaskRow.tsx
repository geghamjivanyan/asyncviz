/**
 * Single row in the live task table.
 *
 * Wrapped in :func:`React.memo` with a custom comparator: the row
 * re-renders only when its signature changes or its selected/depth/
 * column-set differ. The signature catches every visible change in
 * the row's underlying data, so realtime updates flow naturally
 * without rerendering siblings.
 */

import { memo, useCallback, type KeyboardEvent } from "react";
import { cn } from "@/lib/cn";
import { TaskCell } from "@/dashboard/tasks/components/TaskCell";
import { TaskStatusBadge } from "@/dashboard/tasks/components/TaskStatusBadge";
import { TaskDurationCell } from "@/dashboard/tasks/components/TaskDurationCell";
import { TaskTimelineCell } from "@/dashboard/tasks/components/TaskTimelineCell";
import { TaskWarningCell } from "@/dashboard/tasks/components/TaskWarningCell";
import { TaskMetricsCell } from "@/dashboard/tasks/components/TaskMetricsCell";
import { formatStartTime, formatTaskIdShort } from "@/dashboard/tasks/utils/format";
import type { TaskRow as TaskRowData } from "@/dashboard/tasks/models/taskRow";
import type { TaskColumnId } from "@/dashboard/tasks/models/columns";
import { getTaskTableMetrics } from "@/dashboard/tasks/observability/tableMetrics";

export interface TaskRowProps {
  row: TaskRowData;
  visibleColumns: readonly TaskColumnId[];
  selected: boolean;
  onSelect: (taskId: string) => void;
  /** Optional inline style — used by the virtualization layer for
   *  absolute positioning when windowing is enabled. */
  style?: React.CSSProperties;
}

function TaskRowImpl({ row, visibleColumns, selected, onSelect, style }: TaskRowProps) {
  getTaskTableMetrics().recordRowRender();

  const handleSelect = useCallback(() => {
    onSelect(row.taskId);
  }, [onSelect, row.taskId]);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        onSelect(row.taskId);
      }
    },
    [onSelect, row.taskId],
  );

  return (
    <div
      role="row"
      aria-selected={selected}
      data-task-id={row.taskId}
      data-task-status={row.status}
      data-replay={row.isReplay ? "true" : undefined}
      data-orphan={row.isOrphaned ? "true" : undefined}
      tabIndex={0}
      style={style}
      onClick={handleSelect}
      onKeyDown={handleKeyDown}
      className={cn(
        "grid w-full cursor-pointer items-center border-b border-line/40 transition-colors",
        "outline-none focus-visible:ring-1 focus-visible:ring-accent",
        selected ? "bg-elevated text-text" : "text-muted hover:bg-elevated/60",
      )}
    >
      {visibleColumns.map((columnId) => (
        <TaskRowCell key={columnId} columnId={columnId} row={row} />
      ))}
    </div>
  );
}

function TaskRowCell({ columnId, row }: { columnId: TaskColumnId; row: TaskRowData }) {
  switch (columnId) {
    case "status":
      return (
        <TaskCell columnId="status">
          <TaskStatusBadge status={row.status} />
        </TaskCell>
      );
    case "label":
      return (
        <TaskCell columnId="label">
          <span
            style={{ paddingLeft: `${Math.min(row.depth, 12) * 8}px` }}
            className="truncate text-text"
            title={row.label}
          >
            {row.label}
          </span>
          {row.childCount > 0 && (
            <span
              className="shrink-0 text-[10px] text-subtle"
              aria-label={`${row.childCount} children`}
            >
              [{row.childCount}]
            </span>
          )}
        </TaskCell>
      );
    case "coroutine":
      return (
        <TaskCell columnId="coroutine">
          <span className="truncate text-subtle">{row.coroutineName ?? "—"}</span>
        </TaskCell>
      );
    case "duration":
      return <TaskDurationCell durationSeconds={row.durationSeconds} />;
    case "started":
      return (
        <TaskCell columnId="started" align="right" aria-label="Started">
          <span className="tabular-nums text-subtle">{formatStartTime(row.createdAt)}</span>
        </TaskCell>
      );
    case "parent":
      return (
        <TaskCell columnId="parent">
          <span className="truncate text-subtle">{formatTaskIdShort(row.parentTaskId)}</span>
        </TaskCell>
      );
    case "children":
      return (
        <TaskMetricsCell
          childCount={row.childCount}
          recentlyTouched={row.metrics.recentlyTouched}
        />
      );
    case "timeline":
      return <TaskTimelineCell timeline={row.timeline} />;
    case "warnings":
      return <TaskWarningCell warnings={row.warnings} />;
  }
}

function rowEqual(prev: TaskRowProps, next: TaskRowProps): boolean {
  if (prev.row.signature !== next.row.signature) return false;
  if (prev.selected !== next.selected) return false;
  if (prev.onSelect !== next.onSelect) return false;
  if (prev.visibleColumns !== next.visibleColumns) return false;
  if (prev.style !== next.style) return false;
  return true;
}

export const TaskRow = memo(TaskRowImpl, rowEqual);
