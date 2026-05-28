/**
 * Metrics panel — task-scoped roll-ups.
 */

import { memo } from "react";
import { Card } from "@/ui/primitives/Card";
import { cn } from "@/lib/cn";
import { formatDuration, formatPercent } from "@/dashboard/inspector/utils/formatting";
import type { TaskInspection } from "@/dashboard/inspector/models/TaskInspectionModels";

export interface TaskInspectorMetricsProps {
  inspection: TaskInspection;
  className?: string;
}

function TaskInspectorMetricsImpl({ inspection, className }: TaskInspectorMetricsProps) {
  if (inspection.task === null) return null;
  const m = inspection.metrics;
  return (
    <Card
      data-inspector-panel="metrics"
      padding="sm"
      className={cn("flex flex-col gap-2", className)}
    >
      <header>
        <h3 className="font-mono text-xs uppercase tracking-widest text-muted">Metrics</h3>
      </header>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 font-mono text-xs">
        <Row label="Run ratio" value={formatPercent(m.runRatio)} />
        <Row label="Wait ratio" value={formatPercent(m.waitRatio)} />
        <Row label="Avg segment" value={formatDuration(m.averageSegmentSeconds)} />
        <Row label="Max segment" value={formatDuration(m.maxSegmentSeconds)} />
        <Row
          label="Coroutine throughput"
          value={
            m.coroutineThroughputPerSecond === null
              ? "—"
              : `${m.coroutineThroughputPerSecond.toFixed(2)}/s`
          }
        />
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

export const TaskInspectorMetrics = memo(TaskInspectorMetricsImpl);
