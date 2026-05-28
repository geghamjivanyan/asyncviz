import { cn } from "@/lib/cn";
import { TaskCell } from "@/dashboard/tasks/components/TaskCell";
import { formatWarningCount } from "@/dashboard/tasks/utils/format";
import type { TaskRowWarningSummary } from "@/dashboard/tasks/models/taskRow";
import type { WarningSeverity } from "@/types/runtime";

const SEVERITY_DOT: Record<WarningSeverity, string> = {
  info: "bg-accent",
  warning: "bg-warning",
  error: "bg-danger",
  critical: "bg-danger",
};

export interface TaskWarningCellProps {
  warnings: TaskRowWarningSummary;
}

export function TaskWarningCell({ warnings }: TaskWarningCellProps) {
  const severity = warnings.highestSeverity;
  const label =
    warnings.count === 0
      ? "No warnings"
      : `${warnings.count} ${severity ?? "warning"}${warnings.count === 1 ? "" : "s"}`;
  return (
    <TaskCell columnId="warnings" align="left" aria-label={label}>
      <span
        className={cn(
          "inline-flex h-1.5 w-1.5 shrink-0 rounded-full",
          severity === null ? "bg-line" : SEVERITY_DOT[severity],
        )}
        aria-hidden="true"
      />
      <span
        className={cn(
          "tabular-nums",
          warnings.count === 0
            ? "text-subtle"
            : severity === "critical" || severity === "error"
              ? "text-danger"
              : "text-warning",
        )}
      >
        {formatWarningCount(warnings.count)}
      </span>
    </TaskCell>
  );
}
