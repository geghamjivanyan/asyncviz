/**
 * Warnings panel — surfaces active warnings related to the selected
 * task.
 */

import { memo } from "react";
import { Badge } from "@/ui/primitives/Badge";
import { Card } from "@/ui/primitives/Card";
import { cn } from "@/lib/cn";
import { severityIntent } from "@/dashboard/inspector/utils/formatting";
import type { TaskInspection } from "@/dashboard/inspector/models/TaskInspectionModels";

export interface TaskInspectorWarningsProps {
  inspection: TaskInspection;
  className?: string;
}

function TaskInspectorWarningsImpl({ inspection, className }: TaskInspectorWarningsProps) {
  if (inspection.task === null) return null;
  const w = inspection.warnings;
  return (
    <Card
      data-inspector-panel="warnings"
      padding="sm"
      className={cn("flex flex-col gap-2", className)}
    >
      <header className="flex items-center justify-between">
        <h3 className="font-mono text-xs uppercase tracking-widest text-muted">Warnings</h3>
        {w.count > 0 ? (
          <Badge intent={severityIntent(w.highestSeverity)}>{w.count}</Badge>
        ) : null}
      </header>
      {w.active.length === 0 ? (
        <p className="text-[11px] text-subtle">No active warnings.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {w.active.map((warning) => (
            <li
              key={warning.warning_id}
              data-warning-id={warning.warning_id}
              className="rounded border border-line bg-elevated p-2 font-mono text-[11px]"
            >
              <div className="flex items-center gap-2">
                <Badge intent={severityIntent(warning.severity)}>{warning.severity}</Badge>
                <span className="text-muted">{warning.warning_type}</span>
              </div>
              <p className="mt-1 text-text">{warning.message}</p>
              <p className="mt-1 text-subtle">
                Detector: <span className="text-muted">{warning.detector}</span> · Observed{" "}
                <span className="tabular-nums">{warning.occurrence_count}</span>
              </p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export const TaskInspectorWarnings = memo(TaskInspectorWarningsImpl);
