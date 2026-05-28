/**
 * Timeline panel — summarises the selected task's segment timeline.
 */

import { memo } from "react";
import { Badge } from "@/ui/primitives/Badge";
import { Card } from "@/ui/primitives/Card";
import { cn } from "@/lib/cn";
import { formatDuration } from "@/dashboard/inspector/utils/formatting";
import type { TaskInspection } from "@/dashboard/inspector/models/TaskInspectionModels";

export interface TaskInspectorTimelineProps {
  inspection: TaskInspection;
  className?: string;
}

function TaskInspectorTimelineImpl({ inspection, className }: TaskInspectorTimelineProps) {
  if (inspection.task === null) return null;
  const t = inspection.timeline;
  return (
    <Card
      data-inspector-panel="timeline"
      padding="sm"
      className={cn("flex flex-col gap-2", className)}
    >
      <header className="flex items-center justify-between">
        <h3 className="font-mono text-xs uppercase tracking-widest text-muted">Timeline</h3>
        {t.activeSegment ? <Badge intent="success">Active</Badge> : null}
      </header>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 font-mono text-xs">
        <Row label="Total segments" value={t.segmentCount} />
        <Row label="Run segments" value={t.runSegmentCount} />
        <Row label="Wait segments" value={t.waitSegmentCount} />
        <Row label="Run duration" value={formatDuration(t.totalRunSeconds)} />
        <Row label="Wait duration" value={formatDuration(t.totalWaitSeconds)} />
        <Row
          label="First start"
          value={t.firstSegmentStartSeconds === null ? "—" : `${t.firstSegmentStartSeconds.toFixed(3)}s`}
        />
        <Row
          label="Last end"
          value={t.lastSegmentEndSeconds === null ? "—" : `${t.lastSegmentEndSeconds.toFixed(3)}s`}
        />
        <Row
          label="Active segment"
          value={t.activeSegment ? `${t.activeSegment.segment_type} since ${(t.activeSegment.monotonic_start_ns / 1e9).toFixed(3)}s` : "—"}
        />
      </dl>
      {t.recentSegments.length > 0 ? (
        <details className="rounded border border-line bg-elevated p-2">
          <summary className="cursor-pointer text-[10px] uppercase tracking-widest text-subtle">
            Recent segments ({t.recentSegments.length})
          </summary>
          <ul className="mt-2 flex max-h-40 flex-col gap-1 overflow-auto font-mono text-[11px]">
            {t.recentSegments.slice().reverse().map((segment) => (
              <li
                key={segment.segment_id}
                data-segment-row={segment.segment_id}
                className="flex justify-between"
              >
                <span
                  className={
                    segment.segment_type === "run" ? "text-success" : "text-warning"
                  }
                >
                  {segment.segment_type}
                </span>
                <span className="tabular-nums">
                  {formatDuration(segment.duration_ns / 1e9)}
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : (
        <p className="text-[11px] text-subtle">No segments yet.</p>
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

export const TaskInspectorTimeline = memo(TaskInspectorTimelineImpl);
