/**
 * Generic cell wrapper.
 *
 * Every cell in the table is a :class:`TaskCell` so the grid template
 * has identical alignment / overflow behavior across columns.
 */

import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";
import type { TaskColumnId } from "@/dashboard/tasks/models/columns";

export interface TaskCellProps extends HTMLAttributes<HTMLDivElement> {
  columnId: TaskColumnId;
  align?: "left" | "right";
  children: ReactNode;
}

export function TaskCell({
  columnId,
  align = "left",
  className,
  children,
  ...rest
}: TaskCellProps) {
  return (
    <div
      role="gridcell"
      data-column={columnId}
      {...rest}
      className={cn(
        "flex min-w-0 items-center gap-1 truncate px-2 font-mono text-xs",
        align === "right" ? "justify-end text-right" : "justify-start text-left",
        className,
      )}
    >
      {children}
    </div>
  );
}
