/**
 * Inline status badge for a row.
 *
 * Maps the canonical :type:`TaskRowStatus` to one of the design
 * system intents. The badge stays semantic — screen readers see a
 * verbal status, not just a colored dot.
 */

import { Badge } from "@/ui/primitives/Badge";
import type { Intent } from "@/ui/theme/tokens";
import type { TaskRowStatus } from "@/dashboard/tasks/models/taskRow";

const STATUS_INTENT: Record<TaskRowStatus, Intent> = {
  pending: "default",
  running: "success",
  waiting: "accent",
  completed: "default",
  cancelled: "warning",
  failed: "danger",
  replaying: "accent",
  orphaned: "warning",
};

const STATUS_LABEL: Record<TaskRowStatus, string> = {
  pending: "pending",
  running: "running",
  waiting: "waiting",
  completed: "completed",
  cancelled: "cancelled",
  failed: "failed",
  replaying: "replay",
  orphaned: "orphan",
};

export interface TaskStatusBadgeProps {
  status: TaskRowStatus;
}

export function TaskStatusBadge({ status }: TaskStatusBadgeProps) {
  return (
    <Badge
      intent={STATUS_INTENT[status]}
      data-task-status={status}
      aria-label={`Status: ${STATUS_LABEL[status]}`}
    >
      {STATUS_LABEL[status]}
    </Badge>
  );
}
