/**
 * Loading state — surfaced when the runtime store hasn't hydrated
 * the selected task yet.
 */

import { memo } from "react";
import { cn } from "@/lib/cn";

export interface TaskInspectorLoadingProps {
  className?: string;
}

function TaskInspectorLoadingImpl({ className }: TaskInspectorLoadingProps) {
  return (
    <div
      data-task-inspector-loading="true"
      role="status"
      aria-live="polite"
      className={cn(
        "flex h-full items-center justify-center p-6 font-mono text-xs text-muted",
        className,
      )}
    >
      Loading task details…
    </div>
  );
}

export const TaskInspectorLoading = memo(TaskInspectorLoadingImpl);
