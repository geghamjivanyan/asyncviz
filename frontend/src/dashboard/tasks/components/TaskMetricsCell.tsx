import { cn } from "@/lib/cn";
import { TaskCell } from "@/dashboard/tasks/components/TaskCell";

export interface TaskMetricsCellProps {
  childCount: number;
  recentlyTouched: boolean;
}

export function TaskMetricsCell({ childCount, recentlyTouched }: TaskMetricsCellProps) {
  return (
    <TaskCell columnId="children" align="right" aria-label={`Children: ${childCount}`}>
      <span className={cn("tabular-nums", recentlyTouched ? "text-accent" : "text-subtle")}>
        {childCount}
      </span>
    </TaskCell>
  );
}
