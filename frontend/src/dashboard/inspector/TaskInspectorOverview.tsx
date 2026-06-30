/**
 * Overview panel — the at-a-glance summary the user sees first.
 */

import { memo } from "react";
import { Badge } from "@/ui/primitives/Badge";
import { Card } from "@/ui/primitives/Card";
import { cn } from "@/lib/cn";
import {
  formatDuration,
  formatLifecycleState,
  formatPercent,
  formatWallTime,
  severityIntent,
  shortenIdentifier,
} from "@/dashboard/inspector/utils/formatting";
import type { TaskInspection } from "@/dashboard/inspector/models/TaskInspectionModels";

export interface TaskInspectorOverviewProps {
  inspection: TaskInspection;
  className?: string;
}

function TaskInspectorOverviewImpl({ inspection, className }: TaskInspectorOverviewProps) {
  if (inspection.task === null) return null;
  const task = inspection.task;
  return (
    <Card
      data-inspector-panel="overview"
      className={cn("flex flex-col gap-2", className)}
      padding="sm"
    >
      <header className="flex items-center justify-between">
        <h3 className="font-mono text-xs uppercase tracking-widest text-muted">Overview</h3>
        <Badge intent={badgeIntentForState(inspection.state)}>
          {formatLifecycleState(inspection.state)}
        </Badge>
      </header>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 font-mono text-xs">
        <Row label="Task id" value={shortenIdentifier(task.task_id)} />
        <Row label="Asyncio id" value={task.asyncio_task_id ?? "—"} />
        <Row label="Name" value={task.task_name ?? "—"} />
        <Row label="Coroutine" value={task.coroutine_name ?? "—"} />
        <Row label="Created" value={formatWallTime(task.created_at)} />
        <Row label="Updated" value={formatWallTime(task.updated_at)} />
        <Row label="Duration" value={formatDuration(inspection.lifecycle.durationSeconds)} />
        <Row label="Segments" value={formatSegmentsValue(inspection)} />
        <Row label="Run ratio" value={formatPercent(inspection.metrics.runRatio)} />
        <Row label="Wait ratio" value={formatPercent(inspection.metrics.waitRatio)} />
        <Row
          label="Warnings"
          value={
            inspection.warnings.count > 0 ? (
              <Badge intent={severityIntent(inspection.warnings.highestSeverity)}>
                {inspection.warnings.count} {inspection.warnings.highestSeverity ?? ""}
              </Badge>
            ) : (
              "none"
            )
          }
        />
        <Row label="Depth" value={inspection.relationships.depth} />
      </dl>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <>
      <dt className="text-[10px] uppercase tracking-widest text-subtle">{label}</dt>
      <dd className="tabular-nums text-text">{value}</dd>
    </>
  );
}

/** Surface a "no segment data" annotation when a terminal task with a
 *  non-zero duration has no closed or active segments — without it the
 *  raw "0" reads as "task did nothing" instead of "we never saw a
 *  segment". */
function formatSegmentsValue(inspection: TaskInspection): React.ReactNode {
  const count = inspection.timeline.segmentCount;
  if (count > 0) return count;
  const duration = inspection.lifecycle.durationSeconds;
  const segmentless = inspection.lifecycle.terminal && duration !== null && duration > 0;
  if (!segmentless) return count;
  return (
    <span className="inline-flex items-baseline gap-2">
      <span>{count}</span>
      <span className="text-[10px] uppercase tracking-widest text-muted">no segment data</span>
    </span>
  );
}

function badgeIntentForState(
  state: TaskInspection["state"],
): "default" | "accent" | "success" | "warning" | "danger" {
  switch (state) {
    case "running":
      return "success";
    case "waiting":
      return "warning";
    case "completed":
      return "default";
    case "cancelled":
      return "warning";
    case "failed":
      return "danger";
    case "created":
      return "accent";
    default:
      return "default";
  }
}

export const TaskInspectorOverview = memo(TaskInspectorOverviewImpl);
