/**
 * Relationships panel — surfaces lineage + child counts.
 */

import { memo } from "react";
import { Badge } from "@/ui/primitives/Badge";
import { Card } from "@/ui/primitives/Card";
import { cn } from "@/lib/cn";
import { shortenIdentifier } from "@/dashboard/inspector/utils/formatting";
import type { TaskInspection } from "@/dashboard/inspector/models/TaskInspectionModels";

export interface TaskInspectorRelationshipsProps {
  inspection: TaskInspection;
  /** Optional click handler — used by the container to navigate
   *  selection between related tasks. */
  onSelectTask?: (taskId: string) => void;
  className?: string;
}

function TaskInspectorRelationshipsImpl({
  inspection,
  onSelectTask,
  className,
}: TaskInspectorRelationshipsProps) {
  if (inspection.task === null) return null;
  const r = inspection.relationships;
  return (
    <Card
      data-inspector-panel="relationships"
      padding="sm"
      className={cn("flex flex-col gap-2", className)}
    >
      <header className="flex items-center justify-between">
        <h3 className="font-mono text-xs uppercase tracking-widest text-muted">Relationships</h3>
        <Badge>Depth {r.depth}</Badge>
      </header>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 font-mono text-xs">
        <Row label="Parent" value={renderTaskRef(r.parentTaskId, onSelectTask)} />
        <Row label="Root" value={renderTaskRef(r.rootTaskId, onSelectTask)} />
        <Row label="Children" value={r.childTaskIds.length} />
        <Row label="Siblings" value={r.siblingCount} />
        <Row label="Ancestors" value={r.ancestorChain.length} />
      </dl>
      {r.childTaskIds.length > 0 ? (
        <div className="rounded border border-line bg-elevated p-2">
          <p className="text-[10px] uppercase tracking-widest text-subtle">Child tasks</p>
          <ul className="mt-1 flex flex-wrap gap-1 font-mono text-[11px]">
            {r.childTaskIds.slice(0, 32).map((id) => (
              <li key={id}>
                <button
                  type="button"
                  className="rounded border border-line bg-canvas px-1.5 py-0.5 text-text hover:border-accent hover:text-accent"
                  data-relationship-child={id}
                  onClick={() => onSelectTask?.(id)}
                >
                  {shortenIdentifier(id)}
                </button>
              </li>
            ))}
            {r.childTaskIds.length > 32 ? (
              <li className="text-subtle">+{r.childTaskIds.length - 32} more</li>
            ) : null}
          </ul>
        </div>
      ) : null}
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

function renderTaskRef(taskId: string | null, onSelectTask?: (taskId: string) => void) {
  if (taskId === null) return "—";
  if (onSelectTask === undefined) return shortenIdentifier(taskId);
  return (
    <button
      type="button"
      data-relationship-link={taskId}
      onClick={() => onSelectTask(taskId)}
      className="rounded text-accent hover:underline"
    >
      {shortenIdentifier(taskId)}
    </button>
  );
}

export const TaskInspectorRelationships = memo(TaskInspectorRelationshipsImpl);
