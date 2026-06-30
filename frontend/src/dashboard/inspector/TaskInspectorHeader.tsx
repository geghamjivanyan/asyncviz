/**
 * Inspector header — task label + state badge + the canonical
 * "clear / focus" actions.
 */

import { memo } from "react";
import { Badge } from "@/ui/primitives/Badge";
import { cn } from "@/lib/cn";
import { formatLifecycleState, shortenIdentifier } from "@/dashboard/inspector/utils/formatting";
import type { TaskInspection } from "@/dashboard/inspector/models/TaskInspectionModels";

export interface TaskInspectorHeaderProps {
  inspection: TaskInspection;
  onFocus?: () => void;
  onCenter?: () => void;
  onClear?: () => void;
  className?: string;
}

function TaskInspectorHeaderImpl({
  inspection,
  onFocus,
  onCenter,
  onClear,
  className,
}: TaskInspectorHeaderProps) {
  if (inspection.task === null) return null;
  const task = inspection.task;
  const label = task.task_name ?? task.coroutine_name ?? shortenIdentifier(task.task_id);
  return (
    <header
      data-task-inspector-header="true"
      className={cn("flex flex-col gap-2 border-b border-line bg-panel px-3 py-2", className)}
    >
      <div className="flex items-center gap-2">
        <h2 className="truncate font-mono text-sm text-text" title={task.task_id}>
          {label}
        </h2>
        <Badge>{formatLifecycleState(inspection.state)}</Badge>
        {inspection.warnings.count > 0 ? (
          <Badge intent="warning">{inspection.warnings.count} warn</Badge>
        ) : null}
        <span className="ml-auto flex items-center gap-1">
          {onFocus ? (
            <HeaderButton onClick={onFocus} ariaLabel="Fit timeline to task">
              Fit
            </HeaderButton>
          ) : null}
          {onCenter ? (
            <HeaderButton onClick={onCenter} ariaLabel="Center timeline on task">
              Center
            </HeaderButton>
          ) : null}
          {onClear ? (
            <HeaderButton onClick={onClear} ariaLabel="Clear inspection">
              Clear
            </HeaderButton>
          ) : null}
        </span>
      </div>
      <p className="font-mono text-[10px] text-subtle">{task.task_id}</p>
    </header>
  );
}

function HeaderButton({
  onClick,
  ariaLabel,
  children,
}: {
  onClick: () => void;
  ariaLabel: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      data-inspector-action={ariaLabel}
      className={cn(
        "rounded border border-line bg-canvas px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-text",
        "hover:border-accent hover:text-accent",
      )}
    >
      {children}
    </button>
  );
}

export const TaskInspectorHeader = memo(TaskInspectorHeaderImpl);
