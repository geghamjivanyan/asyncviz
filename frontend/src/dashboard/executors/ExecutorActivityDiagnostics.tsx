/**
 * Diagnostics sub-panel for the executor activity system.
 */

import { memo, useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import {
  getExecutorActivityPanelMetrics,
  type ExecutorActivityPanelMetricsSnapshot,
} from "@/dashboard/executors/diagnostics/ExecutorActivityMetricsCollector";
import {
  getExecutorActivityTrace,
  isExecutorActivityTraceEnabled,
  setExecutorActivityTraceEnabled,
} from "@/dashboard/executors/diagnostics/ExecutorActivityTracing";
import {
  useExecutorActivitySelfMetrics,
  useExecutorActivityStats,
} from "@/dashboard/executors/selectors/ExecutorActivitySelectors";

export interface ExecutorActivityDiagnosticsProps {
  pollIntervalMs?: number;
  className?: string;
}

function ExecutorActivityDiagnosticsImpl({
  pollIntervalMs = 1000,
  className,
}: ExecutorActivityDiagnosticsProps): JSX.Element {
  const selfMetrics = useExecutorActivitySelfMetrics();
  const storeStats = useExecutorActivityStats();
  const [panelSnap, setPanelSnap] = useState<ExecutorActivityPanelMetricsSnapshot>(
    () => getExecutorActivityPanelMetrics().snapshot(),
  );
  const [tracingEnabled, setTracingEnabled] = useState(
    isExecutorActivityTraceEnabled(),
  );

  useEffect(() => {
    const timer = window.setInterval(() => {
      setPanelSnap(getExecutorActivityPanelMetrics().snapshot());
    }, pollIntervalMs);
    return () => window.clearInterval(timer);
  }, [pollIntervalMs]);

  const trace = tracingEnabled ? getExecutorActivityTrace() : [];

  return (
    <section
      data-testid="executor-activity-diagnostics"
      className={cn("executor-activity-diagnostics", className)}
    >
      <header className="executor-activity-diagnostics__header">
        <h3>Executor activity</h3>
        <label className="executor-activity-diagnostics__toggle">
          <input
            type="checkbox"
            checked={tracingEnabled}
            onChange={(e) => {
              const next = e.target.checked;
              setExecutorActivityTraceEnabled(next);
              setTracingEnabled(next);
            }}
          />
          Tracing
        </label>
      </header>

      <div className="executor-activity-diagnostics__grid">
        <DiagnosticsSection title="Frontend panel">
          <DiagnosticsRow label="hydrations" value={panelSnap.hydrations} />
          <DiagnosticsRow label="hydration failures" value={panelSnap.hydrationFailures} />
          <DiagnosticsRow label="websocket events" value={panelSnap.websocketEvents} />
          <DiagnosticsRow label="cards rendered" value={panelSnap.cardsRendered} />
          <DiagnosticsRow label="markers rendered" value={panelSnap.markersRendered} />
          <DiagnosticsRow label="selection changes" value={panelSnap.selectionChanges} />
          <DiagnosticsRow label="inspector reveals" value={panelSnap.inspectorReveals} />
        </DiagnosticsSection>

        <DiagnosticsSection title="Store stats">
          <DiagnosticsRow label="hydrations applied" value={storeStats.hydrationsApplied} />
          <DiagnosticsRow label="events applied" value={storeStats.eventsApplied} />
          <DiagnosticsRow label="events dropped" value={storeStats.eventsDropped} />
          <DiagnosticsRow label="markers appended" value={storeStats.markersAppended} />
          <DiagnosticsRow label="markers evicted" value={storeStats.markersEvicted} />
        </DiagnosticsSection>

        <DiagnosticsSection title="Backend engine">
          {selfMetrics === null ? (
            <p className="executor-activity-diagnostics__placeholder">
              No snapshot yet.
            </p>
          ) : (
            <>
              <DiagnosticsRow label="events observed" value={selfMetrics.events_observed} />
              <DiagnosticsRow label="events ignored" value={selfMetrics.events_ignored} />
              <DiagnosticsRow label="events dropped" value={selfMetrics.events_dropped} />
              <DiagnosticsRow label="updates emitted" value={selfMetrics.updates_emitted} />
              <DiagnosticsRow
                label="saturation transitions"
                value={selfMetrics.saturation_transitions}
              />
              <DiagnosticsRow
                label="contention detections"
                value={selfMetrics.contention_detections}
              />
              <DiagnosticsRow
                label="latency spike detections"
                value={selfMetrics.latency_spike_detections}
              />
              <DiagnosticsRow label="tracked executors" value={selfMetrics.tracked_executors} />
              <DiagnosticsRow label="executors evicted" value={selfMetrics.executors_evicted} />
            </>
          )}
        </DiagnosticsSection>
      </div>

      {trace.length > 0 && (
        <div className="executor-activity-diagnostics__trace">
          <h4>Recent trace</h4>
          <ul>
            {trace.slice(-32).map((entry, idx) => (
              <li key={`${entry.at}-${idx}`}>
                <span className="executor-activity-diagnostics__trace-kind">
                  {entry.kind}
                </span>
                <span className="executor-activity-diagnostics__trace-detail">
                  {entry.detail}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

const DiagnosticsSection = memo(function DiagnosticsSectionImpl({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="executor-activity-diagnostics__section">
      <h4>{title}</h4>
      <dl>{children}</dl>
    </div>
  );
});

const DiagnosticsRow = memo(function DiagnosticsRowImpl({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  return (
    <div className="executor-activity-diagnostics__row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
});

export const ExecutorActivityDiagnostics = memo(ExecutorActivityDiagnosticsImpl);
