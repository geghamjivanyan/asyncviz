/**
 * Diagnostics card for the freeze-region layer.
 *
 * Polls the metrics + tracer singletons once per second so operators
 * can verify the renderer is firing as expected. Same shape as the
 * blocking-warning diagnostics card.
 */

import { useEffect, useState } from "react";
import { useFreezeRegionStore } from "@/dashboard/timeline/freeze_regions/FreezeRegionStore";
import {
  getFreezeRegionMetrics,
  type FreezeRegionMetricsSnapshot,
} from "@/dashboard/timeline/freeze_regions/diagnostics/FreezeRegionMetricsCollector";
import {
  getFreezeRegionTraceSnapshot,
  isFreezeRegionTraceEnabled,
  setFreezeRegionTraceEnabled,
  type FreezeRegionTraceEntry,
} from "@/dashboard/timeline/freeze_regions/diagnostics/FreezeRegionTracing";

const POLL_INTERVAL_MS = 1000;
const MAX_TRACE_ROWS = 8;

export function FreezeRegionDiagnostics() {
  const selectedGroupId = useFreezeRegionStore((s) => s.selectedGroupId);
  const hiddenCount = useFreezeRegionStore((s) => s.hiddenCount);
  const reducedMotion = useFreezeRegionStore((s) => s.reducedMotion);

  const [snap, setSnap] = useState<FreezeRegionMetricsSnapshot>(() =>
    getFreezeRegionMetrics().snapshot(),
  );
  const [trace, setTrace] = useState<readonly FreezeRegionTraceEntry[]>(() =>
    getFreezeRegionTraceSnapshot(),
  );
  const [traceEnabled, setTraceEnabledState] = useState<boolean>(() =>
    isFreezeRegionTraceEnabled(),
  );

  useEffect(() => {
    const handle = window.setInterval(() => {
      setSnap(getFreezeRegionMetrics().snapshot());
      setTrace(getFreezeRegionTraceSnapshot());
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(handle);
  }, []);

  const toggleTrace = () => {
    const next = !traceEnabled;
    setFreezeRegionTraceEnabled(next);
    setTraceEnabledState(next);
  };

  return (
    <div data-testid="freeze-region-diagnostics" className="flex flex-col gap-2">
      <h2 className="font-mono text-xs uppercase tracking-widest text-subtle">
        Freeze Regions
      </h2>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 font-mono text-xs">
        <dt className="text-muted">frames</dt>
        <dd className="text-text">{snap.framesRendered}</dd>
        <dt className="text-muted">last visible</dt>
        <dd className="text-text">
          {snap.lastVisibleCount} ({hiddenCount} hidden)
        </dd>
        <dt className="text-muted">projected</dt>
        <dd className="text-text">{snap.freezesProjected}</dd>
        <dt className="text-muted">culled</dt>
        <dd className="text-text">{snap.freezesCulled}</dd>
        <dt className="text-muted">cap trunc</dt>
        <dd className="text-text">{snap.visibleCapTruncations}</dd>
        <dt className="text-muted">selections</dt>
        <dd className="text-text">{snap.selectionChanges}</dd>
        <dt className="text-muted">hovers</dt>
        <dd className="text-text">{snap.hoverChanges}</dd>
        <dt className="text-muted">reveals</dt>
        <dd className="text-text">{snap.revealCalls}</dd>
        <dt className="text-muted">avg frame</dt>
        <dd className="text-text">
          {snap.averageFrameDurationMs.toFixed(2)} ms · max{" "}
          {snap.maxFrameDurationMs.toFixed(2)} ms
        </dd>
        <dt className="text-muted">selected</dt>
        <dd className="text-text">{selectedGroupId ?? "<none>"}</dd>
        <dt className="text-muted">reduced motion</dt>
        <dd className="text-text">{reducedMotion ? "on" : "off"}</dd>
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
          data-testid="freeze-region-trace-toggle"
        >
          {traceEnabled ? "on" : "off"}
        </button>
      </div>
      {traceEnabled && trace.length > 0 ? (
        <ol
          className="max-h-32 overflow-auto font-mono text-[10px]"
          data-testid="freeze-region-trace-list"
        >
          {trace.slice(-MAX_TRACE_ROWS).map((entry, index) => (
            <li
              key={`${entry.atMs}-${index}`}
              className="flex items-center gap-2"
            >
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
