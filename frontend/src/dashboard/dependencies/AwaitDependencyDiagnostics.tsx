/**
 * Diagnostics sub-panel for the dependency-graph system.
 *
 * Surfaces frontend counters, store stats, and an optional trace tail.
 */

import { memo, useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import {
  getAwaitDependencyPanelMetrics,
  type AwaitDependencyMetricsSnapshot,
} from "@/dashboard/dependencies/diagnostics/AwaitDependencyMetricsCollector";
import {
  getAwaitDependencyTrace,
  isAwaitDependencyTraceEnabled,
  setAwaitDependencyTraceEnabled,
} from "@/dashboard/dependencies/diagnostics/AwaitDependencyTracing";
import { useAwaitDependencyStats } from "@/dashboard/dependencies/selectors/AwaitDependencySelectors";

export interface AwaitDependencyDiagnosticsProps {
  pollIntervalMs?: number;
  className?: string;
}

function AwaitDependencyDiagnosticsImpl({
  pollIntervalMs = 1000,
  className,
}: AwaitDependencyDiagnosticsProps): JSX.Element {
  const stats = useAwaitDependencyStats();
  const [panelSnap, setPanelSnap] = useState<AwaitDependencyMetricsSnapshot>(() =>
    getAwaitDependencyPanelMetrics().snapshot(),
  );
  const [tracingEnabled, setTracingEnabled] = useState(isAwaitDependencyTraceEnabled());

  useEffect(() => {
    const timer = window.setInterval(() => {
      setPanelSnap(getAwaitDependencyPanelMetrics().snapshot());
    }, pollIntervalMs);
    return () => window.clearInterval(timer);
  }, [pollIntervalMs]);

  const trace = tracingEnabled ? getAwaitDependencyTrace() : [];

  return (
    <section
      data-testid="await-dependency-diagnostics"
      className={cn("await-dependency-diagnostics", className)}
    >
      <header className="await-dependency-diagnostics__header">
        <h3>Await dependencies</h3>
        <label className="await-dependency-diagnostics__toggle">
          <input
            type="checkbox"
            checked={tracingEnabled}
            onChange={(e) => {
              const next = e.target.checked;
              setAwaitDependencyTraceEnabled(next);
              setTracingEnabled(next);
            }}
          />
          Tracing
        </label>
      </header>

      <div className="await-dependency-diagnostics__grid">
        <DiagnosticsSection title="Render">
          <DiagnosticsRow label="websocket events" value={panelSnap.websocketEvents} />
          <DiagnosticsRow label="layouts computed" value={panelSnap.layoutsComputed} />
          <DiagnosticsRow label="frames rendered" value={panelSnap.framesRendered} />
          <DiagnosticsRow label="nodes rendered" value={panelSnap.nodesRendered} />
          <DiagnosticsRow label="edges rendered" value={panelSnap.edgesRendered} />
          <DiagnosticsRow label="selection changes" value={panelSnap.selectionChanges} />
          <DiagnosticsRow label="inspector reveals" value={panelSnap.inspectorReveals} />
        </DiagnosticsSection>

        <DiagnosticsSection title="Store stats">
          <DiagnosticsRow label="events applied" value={stats.eventsApplied} />
          <DiagnosticsRow label="events dropped" value={stats.eventsDropped} />
          <DiagnosticsRow label="nodes created" value={stats.nodesCreated} />
          <DiagnosticsRow label="edges created" value={stats.edgesCreated} />
          <DiagnosticsRow label="nodes evicted" value={stats.nodesEvicted} />
        </DiagnosticsSection>
      </div>

      {trace.length > 0 && (
        <div className="await-dependency-diagnostics__trace">
          <h4>Recent trace</h4>
          <ul>
            {trace.slice(-32).map((entry, idx) => (
              <li key={`${entry.at}-${idx}`}>
                <span className="await-dependency-diagnostics__trace-kind">{entry.kind}</span>
                <span className="await-dependency-diagnostics__trace-detail">{entry.detail}</span>
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
    <div className="await-dependency-diagnostics__section">
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
    <div className="await-dependency-diagnostics__row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
});

export const AwaitDependencyDiagnostics = memo(AwaitDependencyDiagnosticsImpl);
