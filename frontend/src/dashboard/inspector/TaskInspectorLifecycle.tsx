/**
 * Lifecycle panel — surfaces the canonical lifecycle transition
 * history.
 */

import { memo } from "react";
import { Card } from "@/ui/primitives/Card";
import { cn } from "@/lib/cn";
import {
  formatLifecycleState,
  formatWallTime,
} from "@/dashboard/inspector/utils/formatting";
import type { TaskInspection } from "@/dashboard/inspector/models/TaskInspectionModels";

export interface TaskInspectorLifecycleProps {
  inspection: TaskInspection;
  className?: string;
}

function TaskInspectorLifecycleImpl({ inspection, className }: TaskInspectorLifecycleProps) {
  if (inspection.task === null) return null;
  const l = inspection.lifecycle;
  return (
    <Card
      data-inspector-panel="lifecycle"
      padding="sm"
      className={cn("flex flex-col gap-2", className)}
    >
      <header>
        <h3 className="font-mono text-xs uppercase tracking-widest text-muted">Lifecycle</h3>
      </header>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 font-mono text-xs">
        <Row label="Current state" value={formatLifecycleState(l.state)} />
        <Row label="Terminal" value={l.terminal ? "yes" : "no"} />
        <Row label="Active segment" value={l.active ? "yes" : "no"} />
        <Row label="Created" value={formatWallTime(l.createdAtSeconds)} />
        <Row label="Completed" value={formatWallTime(l.completedAtSeconds)} />
      </dl>
      {l.transitions.length > 0 ? (
        <ul className="flex max-h-40 flex-col gap-1 overflow-auto font-mono text-[11px]">
          {l.transitions.map((transition) => (
            <li
              key={transition.event_id}
              data-transition-id={transition.event_id}
              className="flex justify-between"
            >
              <span className="text-text">{formatLifecycleState(transition.state)}</span>
              <span className="tabular-nums text-subtle">
                {(transition.monotonic_ns / 1e9).toFixed(3)}s
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-[11px] text-subtle">No transitions recorded yet.</p>
      )}
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

export const TaskInspectorLifecycle = memo(TaskInspectorLifecycleImpl);
