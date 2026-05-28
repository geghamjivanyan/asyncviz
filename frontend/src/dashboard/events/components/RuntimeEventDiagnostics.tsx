/**
 * Inline diagnostics panel for the runtime event feed.
 *
 * Polls :class:`EventFeedMetrics` and renders the snapshot.
 */

import { useEffect, useState } from "react";
import { Badge } from "@/ui/primitives/Badge";
import {
  getEventFeedMetrics,
  type EventFeedMetricsSnapshot,
} from "@/dashboard/events/observability";

const POLL_MS = 1000;

export function RuntimeEventDiagnostics() {
  const [snapshot, setSnapshot] = useState<EventFeedMetricsSnapshot>(() =>
    getEventFeedMetrics().snapshot(),
  );
  useEffect(() => {
    const handle = window.setInterval(() => {
      setSnapshot(getEventFeedMetrics().snapshot());
    }, POLL_MS);
    return () => window.clearInterval(handle);
  }, []);
  return (
    <section
      data-event-diagnostics="true"
      aria-label="Event feed diagnostics"
      className="flex flex-col gap-2 p-3 font-mono text-xs text-muted"
    >
      <header className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-widest text-muted">
          Event feed diagnostics
        </span>
        <Badge intent={snapshot.renderStormWarnings > 0 ? "warning" : "default"}>
          {snapshot.renderStormWarnings > 0 ? "render-pressure" : "stable"}
        </Badge>
      </header>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
        <Stat label="Projections" value={snapshot.projectionRebuilds} />
        <Stat label="Pipeline runs" value={snapshot.pipelineRuns} />
        <Stat label="Group rebuilds" value={snapshot.groupRebuilds} />
        <Stat label="Filter evals" value={snapshot.filterEvaluations} />
        <Stat label="Row renders" value={snapshot.rowRenders} />
        <Stat label="Live appends" value={snapshot.liveAppends} />
        <Stat label="Replay appends" value={snapshot.replayAppends} />
        <Stat label="Rows projected" value={snapshot.rowsProjectedTotal} />
        <Stat label="Last pipeline ms" value={snapshot.lastPipelineMs.toFixed(2)} />
        <Stat label="Max pipeline ms" value={snapshot.maxPipelineMs.toFixed(2)} />
        <Stat label="Last projection ms" value={snapshot.lastProjectionMs.toFixed(2)} />
        <Stat label="Max projection ms" value={snapshot.maxProjectionMs.toFixed(2)} />
        <Stat label="Storm warnings" value={snapshot.renderStormWarnings} />
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
