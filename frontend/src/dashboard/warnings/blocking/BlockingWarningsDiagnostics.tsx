/**
 * Diagnostics card for the blocking-warnings panel.
 *
 * Surfaced from the central :func:`DiagnosticsPage` so operators can
 * peek at live counters + the recent trace ring without leaving the
 * page. Polls the singletons once per second — the same cadence the
 * other diagnostics cards use.
 */

import { useEffect, useState } from "react";
import { useBlockingWarningStore } from "@/dashboard/warnings/blocking/BlockingWarningStore";
import {
  getBlockingWarningPanelMetrics,
  type BlockingWarningPanelMetricsSnapshot,
} from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningMetricsCollector";
import {
  getBlockingWarningTraceSnapshot,
  isBlockingWarningTraceEnabled,
  setBlockingWarningTraceEnabled,
  type BlockingWarningTraceEntry,
} from "@/dashboard/warnings/blocking/diagnostics/BlockingWarningTracing";

const POLL_INTERVAL_MS = 1000;
const MAX_TRACE_ROWS = 8;

export function BlockingWarningsDiagnostics() {
  const stats = useBlockingWarningStore((s) => s.stats);
  const status = useBlockingWarningStore((s) => s.status);
  const lastSequence = useBlockingWarningStore((s) => s.lastSequence);

  const [panelStats, setPanelStats] = useState<BlockingWarningPanelMetricsSnapshot>(() =>
    getBlockingWarningPanelMetrics().snapshot(),
  );
  const [trace, setTrace] = useState<readonly BlockingWarningTraceEntry[]>(() =>
    getBlockingWarningTraceSnapshot(),
  );
  const [traceEnabled, setTraceEnabledState] = useState<boolean>(() =>
    isBlockingWarningTraceEnabled(),
  );

  useEffect(() => {
    const handle = window.setInterval(() => {
      setPanelStats(getBlockingWarningPanelMetrics().snapshot());
      setTrace(getBlockingWarningTraceSnapshot());
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(handle);
  }, []);

  const toggleTrace = () => {
    const next = !traceEnabled;
    setBlockingWarningTraceEnabled(next);
    setTraceEnabledState(next);
  };

  return (
    <div data-testid="blocking-warnings-diagnostics" className="flex flex-col gap-2">
      <h2 className="font-mono text-xs uppercase tracking-widest text-subtle">Blocking Warnings</h2>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 font-mono text-xs">
        <dt className="text-muted">status</dt>
        <dd className="text-text">{status}</dd>
        <dt className="text-muted">last seq</dt>
        <dd className="text-text">{lastSequence}</dd>
        <dt className="text-muted">hydrations</dt>
        <dd className="text-text">
          {panelStats.hydrationCount} ({panelStats.hydrationFailures} failed)
        </dd>
        <dt className="text-muted">events</dt>
        <dd className="text-text">
          {panelStats.liveEventsApplied} applied · {panelStats.liveEventsDropped} dropped
        </dd>
        <dt className="text-muted">store events</dt>
        <dd className="text-text">
          applied {stats.eventsApplied} · dup {stats.duplicatesDropped} · stale {stats.staleDropped}
        </dd>
        <dt className="text-muted">filter changes</dt>
        <dd className="text-text">{panelStats.filterChanges}</dd>
        <dt className="text-muted">selections</dt>
        <dd className="text-text">{panelStats.selectionChanges}</dd>
        <dt className="text-muted">avg render</dt>
        <dd className="text-text">
          {panelStats.averageRenderDurationMs.toFixed(2)} ms · max{" "}
          {panelStats.maxRenderDurationMs.toFixed(2)} ms
        </dd>
      </dl>
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-wider text-subtle">
          Trace ring
        </span>
        <button
          type="button"
          onClick={toggleTrace}
          aria-pressed={traceEnabled}
          className="rounded border border-line px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-text hover:border-accent hover:text-accent"
          data-testid="blocking-warnings-trace-toggle"
        >
          {traceEnabled ? "on" : "off"}
        </button>
      </div>
      {traceEnabled && trace.length > 0 ? (
        <ol
          className="max-h-32 overflow-auto font-mono text-[10px]"
          data-testid="blocking-warnings-trace-list"
        >
          {trace.slice(-MAX_TRACE_ROWS).map((entry, index) => (
            <li key={`${entry.atMs}-${index}`} className="flex items-center gap-2">
              <span className="text-subtle">{entry.atMs.toFixed(0)} ms</span>
              <span className="text-text">{entry.kind}</span>
              <span className="text-subtle truncate">{entry.detail}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="font-mono text-[10px] italic text-subtle">
          {traceEnabled ? "No trace entries yet." : "Tracing disabled."}
        </p>
      )}
    </div>
  );
}
