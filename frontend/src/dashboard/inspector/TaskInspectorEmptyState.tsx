/**
 * Empty state — surfaced when no task is selected.
 */

import { memo } from "react";
import { cn } from "@/lib/cn";

export interface TaskInspectorEmptyStateProps {
  className?: string;
}

function TaskInspectorEmptyStateImpl({ className }: TaskInspectorEmptyStateProps) {
  return (
    <div
      data-task-inspector-empty="true"
      role="status"
      className={cn(
        "flex h-full flex-col items-center justify-center gap-1 p-6 text-center font-mono text-xs text-subtle",
        className,
      )}
    >
      <p className="text-[11px] uppercase tracking-widest text-muted">No task selected</p>
      <p>Click a row on the timeline or press ↑/↓ to inspect a task.</p>
    </div>
  );
}

export const TaskInspectorEmptyState = memo(TaskInspectorEmptyStateImpl);
