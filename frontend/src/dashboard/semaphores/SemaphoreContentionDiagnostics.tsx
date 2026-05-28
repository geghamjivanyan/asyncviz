/**
 * Diagnostics sub-panel for the semaphore contention system.
 *
 * Surfaces: panel-side counters, backend engine self-metrics, and a
 * tail of the trace ring when enabled. Used by /diagnostics.
 */

import { memo, useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import {
  getSemaphoreContentionPanelMetrics,
  type SemaphoreContentionPanelMetricsSnapshot,
} from "@/dashboard/semaphores/diagnostics/SemaphoreContentionMetricsCollector";
import {
  getSemaphoreContentionTrace,
  isSemaphoreContentionTraceEnabled,
  setSemaphoreContentionTraceEnabled,
} from "@/dashboard/semaphores/diagnostics/SemaphoreContentionTracing";
import {
  useSemaphoreContentionSelfMetrics,
  useSemaphoreContentionStats,
} from "@/dashboard/semaphores/selectors/SemaphoreContentionSelectors";

export interface SemaphoreContentionDiagnosticsProps {
  pollIntervalMs?: number;
  className?: string;
}

function SemaphoreContentionDiagnosticsImpl({
  pollIntervalMs = 1000,
  className,
}: SemaphoreContentionDiagnosticsProps): JSX.Element {
  const selfMetrics = useSemaphoreContentionSelfMetrics();
  const storeStats = useSemaphoreContentionStats();
  const [panelSnap, setPanelSnap] =
    useState<SemaphoreContentionPanelMetricsSnapshot>(() =>
      getSemaphoreContentionPanelMetrics().snapshot(),
    );
  const [tracingEnabled, setTracingEnabled] = useState(
    isSemaphoreContentionTraceEnabled(),
  );

  useEffect(() => {
    const timer = window.setInterval(() => {
      setPanelSnap(getSemaphoreContentionPanelMetrics().snapshot());
    }, pollIntervalMs);
    return () => window.clearInterval(timer);
  }, [pollIntervalMs]);

  const trace = tracingEnabled ? getSemaphoreContentionTrace() : [];

  return (
    <section
      data-testid="semaphore-contention-diagnostics"
      className={cn("semaphore-contention-diagnostics", className)}
    >
      <header className="semaphore-contention-diagnostics__header">
        <h3>Semaphore contention</h3>
        <label className="semaphore-contention-diagnostics__toggle">
          <input
            type="checkbox"
            checked={tracingEnabled}
            onChange={(e) => {
              const next = e.target.checked;
              setSemaphoreContentionTraceEnabled(next);
              setTracingEnabled(next);
            }}
          />
          Tracing
        </label>
      </header>

      <div className="semaphore-contention-diagnostics__grid">
        <DiagnosticsSection title="Frontend panel">
          <DiagnosticsRow label="hydrations" value={panelSnap.hydrations} />
          <DiagnosticsRow
            label="hydration failures"
            value={panelSnap.hydrationFailures}
          />
          <DiagnosticsRow label="websocket events" value={panelSnap.websocketEvents} />
          <DiagnosticsRow label="cards rendered" value={panelSnap.cardsRendered} />
          <DiagnosticsRow label="markers rendered" value={panelSnap.markersRendered} />
          <DiagnosticsRow label="selection changes" value={panelSnap.selectionChanges} />
          <DiagnosticsRow label="inspector reveals" value={panelSnap.inspectorReveals} />
        </DiagnosticsSection>

        <DiagnosticsSection title="Store stats">
          <DiagnosticsRow
            label="hydrations applied"
            value={storeStats.hydrationsApplied}
          />
          <DiagnosticsRow label="events applied" value={storeStats.eventsApplied} />
          <DiagnosticsRow label="events dropped" value={storeStats.eventsDropped} />
          <DiagnosticsRow
            label="markers appended"
            value={storeStats.markersAppended}
          />
          <DiagnosticsRow label="markers evicted" value={storeStats.markersEvicted} />
        </DiagnosticsSection>

        <DiagnosticsSection title="Backend engine">
          {selfMetrics === null ? (
            <p className="semaphore-contention-diagnostics__placeholder">
              No snapshot yet.
            </p>
          ) : (
            <>
              <DiagnosticsRow
                label="semaphores registered"
                value={selfMetrics.semaphores_registered}
              />
              <DiagnosticsRow
                label="semaphores finalized"
                value={selfMetrics.semaphores_finalized}
              />
              <DiagnosticsRow
                label="events emitted"
                value={selfMetrics.events_emitted}
              />
              <DiagnosticsRow
                label="events dropped"
                value={selfMetrics.events_dropped}
              />
              <DiagnosticsRow
                label="acquire events"
                value={selfMetrics.acquire_events}
              />
              <DiagnosticsRow
                label="release events"
                value={selfMetrics.release_events}
              />
              <DiagnosticsRow
                label="blocked acquires"
                value={selfMetrics.blocked_acquires}
              />
              <DiagnosticsRow
                label="contention detections"
                value={selfMetrics.contention_detections}
              />
              <DiagnosticsRow
                label="cancelled waits"
                value={selfMetrics.cancelled_waits}
              />
            </>
          )}
        </DiagnosticsSection>
      </div>

      {trace.length > 0 && (
        <div className="semaphore-contention-diagnostics__trace">
          <h4>Recent trace</h4>
          <ul>
            {trace.slice(-32).map((entry, idx) => (
              <li key={`${entry.at}-${idx}`}>
                <span className="semaphore-contention-diagnostics__trace-kind">
                  {entry.kind}
                </span>
                <span className="semaphore-contention-diagnostics__trace-detail">
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
    <div className="semaphore-contention-diagnostics__section">
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
    <div className="semaphore-contention-diagnostics__row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
});

export const SemaphoreContentionDiagnostics = memo(SemaphoreContentionDiagnosticsImpl);
