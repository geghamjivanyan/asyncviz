/**
 * Diagnostics sub-panel for the queue pressure system.
 *
 * Surfaces:
 *   * panel-side counters (websocket events received, cards rendered)
 *   * the backend engine's self-metrics snapshot (events_observed,
 *     updates_emitted, pressure_transitions, …)
 *   * a tail of the trace ring (when enabled)
 *
 * Used by /diagnostics — read-only, refreshes on every render.
 */

import { memo, useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import {
  getQueuePressurePanelMetrics,
  type QueuePressurePanelMetricsSnapshot,
} from "@/dashboard/queues/diagnostics/QueuePressureMetricsCollector";
import {
  getQueuePressureTrace,
  isQueuePressureTraceEnabled,
  setQueuePressureTraceEnabled,
} from "@/dashboard/queues/diagnostics/QueuePressureTracing";
import {
  useQueuePressureSelfMetrics,
  useQueuePressureStats,
} from "@/dashboard/queues/selectors/QueuePressureSelectors";

export interface QueuePressureDiagnosticsProps {
  /** Polling interval for the panel metrics snapshot (ms). */
  pollIntervalMs?: number;
  className?: string;
}

function QueuePressureDiagnosticsImpl({
  pollIntervalMs = 1000,
  className,
}: QueuePressureDiagnosticsProps): JSX.Element {
  const selfMetrics = useQueuePressureSelfMetrics();
  const storeStats = useQueuePressureStats();
  const [panelSnap, setPanelSnap] = useState<QueuePressurePanelMetricsSnapshot>(
    () => getQueuePressurePanelMetrics().snapshot(),
  );
  const [tracingEnabled, setTracingEnabled] = useState(isQueuePressureTraceEnabled());

  useEffect(() => {
    const timer = window.setInterval(() => {
      setPanelSnap(getQueuePressurePanelMetrics().snapshot());
    }, pollIntervalMs);
    return () => window.clearInterval(timer);
  }, [pollIntervalMs]);

  const trace = tracingEnabled ? getQueuePressureTrace() : [];

  return (
    <section
      data-testid="queue-pressure-diagnostics"
      className={cn("queue-pressure-diagnostics", className)}
    >
      <header className="queue-pressure-diagnostics__header">
        <h3>Queue pressure</h3>
        <label className="queue-pressure-diagnostics__toggle">
          <input
            type="checkbox"
            checked={tracingEnabled}
            onChange={(e) => {
              const next = e.target.checked;
              setQueuePressureTraceEnabled(next);
              setTracingEnabled(next);
            }}
          />
          Tracing
        </label>
      </header>

      <div className="queue-pressure-diagnostics__grid">
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
            <p className="queue-pressure-diagnostics__placeholder">
              No snapshot yet.
            </p>
          ) : (
            <>
              <DiagnosticsRow label="events observed" value={selfMetrics.events_observed} />
              <DiagnosticsRow label="events ignored" value={selfMetrics.events_ignored} />
              <DiagnosticsRow label="events dropped" value={selfMetrics.events_dropped} />
              <DiagnosticsRow label="updates emitted" value={selfMetrics.updates_emitted} />
              <DiagnosticsRow
                label="pressure transitions"
                value={selfMetrics.pressure_transitions}
              />
              <DiagnosticsRow
                label="contention detections"
                value={selfMetrics.contention_detections}
              />
              <DiagnosticsRow
                label="saturation detections"
                value={selfMetrics.saturation_detections}
              />
              <DiagnosticsRow label="tracked queues" value={selfMetrics.tracked_queues} />
              <DiagnosticsRow label="queues evicted" value={selfMetrics.queues_evicted} />
            </>
          )}
        </DiagnosticsSection>
      </div>

      {trace.length > 0 && (
        <div className="queue-pressure-diagnostics__trace">
          <h4>Recent trace</h4>
          <ul>
            {trace.slice(-32).map((entry, idx) => (
              <li key={`${entry.at}-${idx}`}>
                <span className="queue-pressure-diagnostics__trace-kind">
                  {entry.kind}
                </span>
                <span className="queue-pressure-diagnostics__trace-detail">
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
    <div className="queue-pressure-diagnostics__section">
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
    <div className="queue-pressure-diagnostics__row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
});

export const QueuePressureDiagnostics = memo(QueuePressureDiagnosticsImpl);
