import { formatDuration } from "@/dashboard/tasks/utils/format";
import { TaskCell } from "@/dashboard/tasks/components/TaskCell";

export interface TaskDurationCellProps {
  durationSeconds: number | null;
}

export function TaskDurationCell({ durationSeconds }: TaskDurationCellProps) {
  return (
    <TaskCell columnId="duration" align="right" aria-label="Duration">
      <span className="tabular-nums text-text">{formatDuration(durationSeconds)}</span>
    </TaskCell>
  );
}
