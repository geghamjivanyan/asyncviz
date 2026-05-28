/**
 * Inline diagnostics panel for the live task table.
 *
 * Reads :class:`TaskTableMetrics` and renders the snapshot as a small
 * key/value list. Designed to be embedded inside the diagnostics page
 * or any debug-only surface; not mounted on the default route.
 */

import { useEffect, useState } from "react";
import { Badge } from "@/ui/primitives/Badge";
import { getTaskTableMetrics } from "@/dashboard/tasks/observability/tableMetrics";
import type { TaskTableMetricsSnapshot } from "@/dashboard/tasks/observability/tableMetrics";

const POLL_MS = 1000;

export function TaskDiagnostics() {
  const [snapshot, setSnapshot] = useState<TaskTableMetricsSnapshot>(() =>
    getTaskTableMetrics().snapshot(),
  );
  useEffect(() => {
    // Poll the metrics instance at a steady cadence — the diagnostics
    // page is only mounted by operators, so the cost is negligible.
    const handle = window.setInterval(() => {
      setSnapshot(getTaskTableMetrics().snapshot());
    }, POLL_MS);
    return () => window.clearInterval(handle);
  }, []);
  return (
    <section
      data-task-diagnostics="true"
      aria-label="Task table diagnostics"
      className="flex flex-col gap-2 p-3 font-mono text-xs text-muted"
    >
      <header className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-widest text-muted">
          Task table diagnostics
        </span>
        <Badge intent={snapshot.renderStormWarnings > 0 ? "warning" : "default"}>
          {snapshot.renderStormWarnings > 0 ? "render-pressure" : "stable"}
        </Badge>
      </header>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
        <Stat label="Projections" value={snapshot.projectionRebuilds} />
        <Stat label="Selector evals" value={snapshot.selectorEvaluations} />
        <Stat label="Pipeline runs" value={snapshot.pipelineRuns} />
        <Stat label="Row renders" value={snapshot.rowRenders} />
        <Stat label="Selections" value={snapshot.selectionEvents} />
        <Stat label="Storm warnings" value={snapshot.renderStormWarnings} />
        <Stat label="Last pipeline ms" value={snapshot.lastPipelineMs.toFixed(2)} />
        <Stat label="Max pipeline ms" value={snapshot.maxPipelineMs.toFixed(2)} />
        <Stat label="Last projection ms" value={snapshot.lastProjectionMs.toFixed(2)} />
        <Stat label="Max projection ms" value={snapshot.maxProjectionMs.toFixed(2)} />
      </dl>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <>
      <dt className="text-[10px] uppercase tracking-widest text-subtle">{label}</dt>
      <dd className="tabular-nums text-text">{value}</dd>
    </>
  );
}
