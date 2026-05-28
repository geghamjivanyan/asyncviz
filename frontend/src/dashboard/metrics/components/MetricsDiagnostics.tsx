/**
 * Inline diagnostics panel for the metrics header.
 *
 * Polls :class:`MetricsHeaderMetrics` and renders the snapshot for
 * the diagnostics page.
 */

import { useEffect, useState } from "react";
import { Badge } from "@/ui/primitives/Badge";
import {
  getMetricsHeaderMetrics,
  type MetricsHeaderMetricsSnapshot,
} from "@/dashboard/metrics/observability";

const POLL_MS = 1000;

export function MetricsDiagnostics() {
  const [snapshot, setSnapshot] = useState<MetricsHeaderMetricsSnapshot>(() =>
    getMetricsHeaderMetrics().snapshot(),
  );
  useEffect(() => {
    const handle = window.setInterval(() => {
      setSnapshot(getMetricsHeaderMetrics().snapshot());
    }, POLL_MS);
    return () => window.clearInterval(handle);
  }, []);
  return (
    <section
      data-metrics-diagnostics="true"
      aria-label="Metrics header diagnostics"
      className="flex flex-col gap-2 p-3 font-mono text-xs text-muted"
    >
      <header className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-widest text-muted">
          Metrics header diagnostics
        </span>
        <Badge intent={snapshot.renderStormWarnings > 0 ? "warning" : "default"}>
          {snapshot.renderStormWarnings > 0 ? "render-pressure" : "stable"}
        </Badge>
      </header>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
        <Stat label="Projections" value={snapshot.projectionRebuilds} />
        <Stat label="Card renders" value={snapshot.cardRenders} />
        <Stat label="Phase transitions" value={snapshot.phaseTransitions} />
        <Stat label="Replay transitions" value={snapshot.replayTransitions} />
        <Stat label="Warning aggregations" value={snapshot.warningAggregations} />
        <Stat label="Throughput samples" value={snapshot.throughputSamples} />
        <Stat label="Last selector ms" value={snapshot.lastSelectorMs.toFixed(2)} />
        <Stat label="Max selector ms" value={snapshot.maxSelectorMs.toFixed(2)} />
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
