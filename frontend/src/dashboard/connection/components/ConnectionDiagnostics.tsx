/**
 * Inline diagnostics for the connection-status system.
 *
 * Polls :class:`ConnectionMetrics` at 1Hz and renders the snapshot
 * alongside the connection toolbar + the live history ring.
 */

import { useEffect, useState } from "react";
import { Badge } from "@/ui/primitives/Badge";
import { ConnectionToolbar } from "@/dashboard/connection/components/ConnectionToolbar";
import { ConnectionHistory } from "@/dashboard/connection/components/ConnectionHistory";
import { ConnectionTimeline } from "@/dashboard/connection/components/ConnectionTimeline";
import { useConnectionSummary } from "@/dashboard/connection/hooks/useConnectionSummary";
import { useConnectionHistory } from "@/dashboard/connection/hooks/useConnectionHistory";
import {
  getConnectionMetrics,
  type ConnectionMetricsSnapshot,
} from "@/dashboard/connection/observability";

const POLL_MS = 1000;

export function ConnectionDiagnostics() {
  const summary = useConnectionSummary();
  const history = useConnectionHistory(summary);
  const [metricsSnapshot, setMetricsSnapshot] = useState<ConnectionMetricsSnapshot>(() =>
    getConnectionMetrics().snapshot(),
  );

  useEffect(() => {
    const handle = window.setInterval(() => {
      setMetricsSnapshot(getConnectionMetrics().snapshot());
    }, POLL_MS);
    return () => window.clearInterval(handle);
  }, []);

  return (
    <section
      data-connection-diagnostics="true"
      aria-label="Connection diagnostics"
      className="flex flex-col gap-3 p-3 font-mono text-xs text-muted"
    >
      <header className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-widest text-muted">
          Connection diagnostics
        </span>
        <Badge intent={metricsSnapshot.renderStormWarnings > 0 ? "warning" : "default"}>
          {metricsSnapshot.renderStormWarnings > 0 ? "render-pressure" : "stable"}
        </Badge>
      </header>
      <ConnectionToolbar summary={summary} />
      <ConnectionTimeline entries={history.entries} />
      <ConnectionHistory entries={history.entries} onClear={history.clear} />
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
        <Stat label="Projections" value={metricsSnapshot.projectionRebuilds} />
        <Stat label="Phase changes" value={metricsSnapshot.phaseTransitions} />
        <Stat label="Replay transitions" value={metricsSnapshot.replayTransitions} />
        <Stat label="Hydrations" value={metricsSnapshot.hydrationCompletions} />
        <Stat label="Reconnects" value={metricsSnapshot.reconnectAttempts} />
        <Stat label="Heartbeat stale" value={metricsSnapshot.heartbeatStaleDetections} />
        <Stat label="Heartbeat offline" value={metricsSnapshot.heartbeatOfflineDetections} />
        <Stat label="History appends" value={metricsSnapshot.historyAppends} />
        <Stat label="Indicator renders" value={metricsSnapshot.indicatorRenders} />
        <Stat label="Tooltip renders" value={metricsSnapshot.tooltipRenders} />
        <Stat label="Last selector ms" value={metricsSnapshot.lastSelectorMs.toFixed(2)} />
        <Stat label="Max selector ms" value={metricsSnapshot.maxSelectorMs.toFixed(2)} />
        <Stat label="Storm warnings" value={metricsSnapshot.renderStormWarnings} />
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
