/**
 * Replay panel — surfaces the runtime's replay window state alongside
 * the active live cursor.
 */

import { memo } from "react";
import { Badge } from "@/ui/primitives/Badge";
import { Card } from "@/ui/primitives/Card";
import { cn } from "@/lib/cn";
import { formatSequence } from "@/dashboard/inspector/utils/formatting";
import type { TaskInspection } from "@/dashboard/inspector/models/TaskInspectionModels";

export interface TaskInspectorReplayProps {
  inspection: TaskInspection;
  className?: string;
}

function TaskInspectorReplayImpl({ inspection, className }: TaskInspectorReplayProps) {
  if (inspection.task === null) return null;
  const r = inspection.replay;
  return (
    <Card
      data-inspector-panel="replay"
      padding="sm"
      className={cn("flex flex-col gap-2", className)}
    >
      <header className="flex items-center justify-between">
        <h3 className="font-mono text-xs uppercase tracking-widest text-muted">Replay</h3>
        <Badge intent={r.windowHit ? "success" : "warning"}>
          {r.windowHit ? "window hit" : "cold restart"}
        </Badge>
      </header>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 font-mono text-xs">
        <Row label="Oldest sequence" value={formatSequence(r.oldestRetainedSequence)} />
        <Row label="Newest sequence" value={formatSequence(r.newestRetainedSequence)} />
        <Row label="Live sequence" value={formatSequence(r.lastSequence)} />
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

export const TaskInspectorReplay = memo(TaskInspectorReplayImpl);
