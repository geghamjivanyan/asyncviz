import { cn } from "@/lib/cn";
import { TaskCell } from "@/dashboard/tasks/components/TaskCell";
import type { TaskRowTimelineSummary } from "@/dashboard/tasks/models/taskRow";

export interface TaskTimelineCellProps {
  timeline: TaskRowTimelineSummary;
}

export function TaskTimelineCell({ timeline }: TaskTimelineCellProps) {
  const active = timeline.active;
  return (
    <TaskCell
      columnId="timeline"
      align="left"
      aria-label={active ? "Timeline active" : "Timeline inactive"}
    >
      <span
        className={cn(
          "inline-flex h-1.5 w-1.5 shrink-0 rounded-full",
          active ? "bg-success" : "bg-line",
        )}
        aria-hidden="true"
      />
      <span className="tabular-nums text-subtle">{timeline.closedSegments}</span>
    </TaskCell>
  );
}
