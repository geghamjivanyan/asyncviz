/**
 * Sticky header row.
 *
 * Each cell wires the sortable columns to the shared sort state. The
 * header lives outside the body so the body can own scrolling.
 */

import type { CSSProperties } from "react";
import type { TaskColumnId } from "@/dashboard/tasks/models/columns";
import { COLUMN_LOOKUP } from "@/dashboard/tasks/models/columns";
import type { TaskSortState } from "@/dashboard/tasks/models/filters";
import { cn } from "@/lib/cn";

export interface TaskTableHeaderProps {
  visibleColumns: readonly TaskColumnId[];
  sort: TaskSortState;
  onToggleSort: (columnId: TaskColumnId) => void;
  /** Grid template applied as inline style — produced by :class:`TaskTable`. */
  rowStyle?: CSSProperties;
}

export function TaskTableHeader({
  visibleColumns,
  sort,
  onToggleSort,
  rowStyle,
}: TaskTableHeaderProps) {
  return (
    <div
      role="row"
      style={rowStyle}
      className="sticky top-0 z-10 grid h-8 w-full items-center border-b border-line bg-panel text-[10px] uppercase tracking-widest"
    >
      {visibleColumns.map((columnId) => {
        const col = COLUMN_LOOKUP[columnId];
        const isActive = sort.columnId === columnId;
        const ariaSort: "ascending" | "descending" | "none" = isActive
          ? sort.direction === "asc"
            ? "ascending"
            : "descending"
          : "none";
        const onActivate = () => {
          if (col.sortable) onToggleSort(columnId);
        };
        return (
          <div
            key={columnId}
            role="columnheader"
            data-column={columnId}
            aria-sort={ariaSort}
            aria-label={col.ariaLabel ?? col.label}
            className={cn(
              "flex select-none items-center gap-1 truncate px-2 text-muted",
              col.align === "right" ? "justify-end text-right" : "justify-start text-left",
              col.sortable
                ? "cursor-pointer hover:text-text focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent"
                : "cursor-default",
              isActive && "text-text",
            )}
            tabIndex={col.sortable ? 0 : -1}
            onClick={onActivate}
            onKeyDown={(event) => {
              if (col.sortable && (event.key === "Enter" || event.key === " ")) {
                event.preventDefault();
                onActivate();
              }
            }}
          >
            <span className="truncate">{col.label}</span>
            {isActive && (
              <span aria-hidden="true" className="text-accent">
                {sort.direction === "asc" ? "▲" : "▼"}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
