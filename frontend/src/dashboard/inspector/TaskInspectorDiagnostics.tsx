/**
 * Inspector diagnostics panel — polls the inspector + selection
 * metrics at 1Hz and surfaces them on the diagnostics page.
 */

import { useEffect, useState } from "react";
import {
  getTimelineInspectorMetrics,
  type TaskInspectorMetricsSnapshot,
} from "@/dashboard/inspector/TaskInspectorMetricsCollector";

const POLL_MS = 1000;

export function TaskInspectorDiagnosticsPanel() {
  const [snapshot, setSnapshot] = useState<TaskInspectorMetricsSnapshot>(() =>
    getTimelineInspectorMetrics().snapshot(),
  );
  useEffect(() => {
    const handle = window.setInterval(() => {
      setSnapshot(getTimelineInspectorMetrics().snapshot());
    }, POLL_MS);
    return () => window.clearInterval(handle);
  }, []);
  return (
    <section
      data-task-inspector-diagnostics="true"
      className="flex flex-col gap-2 p-3 font-mono text-xs text-muted"
    >
      <header className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-widest text-muted">Task inspector</span>
      </header>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
        <Stat label="Inspections built" value={snapshot.inspectionsBuilt} />
        <Stat label="Panels rendered" value={snapshot.panelsRendered} />
        <Stat label="Panel switches" value={snapshot.panelSwitches} />
        <Stat label="Reveal calls" value={snapshot.revealCalls} />
        <Stat label="Fit calls" value={snapshot.fitCalls} />
        <Stat label="Warning correlations" value={snapshot.warningCorrelations} />
        <Stat label="Empty-state renders" value={snapshot.emptyStateRenders} />
        <Stat label="Loading-state renders" value={snapshot.loadingStateRenders} />
        <Stat label="Selection rebuilds" value={snapshot.selectionRebuilds} />
        <Stat label="Last projection ms" value={snapshot.lastProjectionMs.toFixed(3)} />
        <Stat label="Max projection ms" value={snapshot.maxProjectionMs.toFixed(3)} />
      </dl>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 border-t border-line pt-2">
        <span className="col-span-2 text-[10px] uppercase tracking-widest text-subtle">
          Panel renders
        </span>
        {Object.entries(snapshot.panelRendersByKind).map(([kind, count]) => (
          <Stat key={kind} label={kind} value={count} />
        ))}
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
