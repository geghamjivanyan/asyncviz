/**
 * Top-level selector — pulls the minimal slices from the runtime
 * store, composes them through :func:`projectConnection`, and returns
 * a stable :type:`ConnectionSummary`.
 *
 * Every consumer (indicator badge, tooltip, history, diagnostics)
 * reads from this summary. The summary identity only changes when
 * something visible changes (see ``signature``); React.memo
 * sub-components short-circuit otherwise.
 */

import { useMemo } from "react";
import { useRuntimeStore } from "@/state/runtime";
import { projectConnection } from "@/dashboard/connection/selectors/projectConnection";
import { useNowMs } from "@/dashboard/connection/hooks/useNowMs";
import type { ConnectionSummary } from "@/dashboard/connection/models/state";
import { getConnectionMetrics } from "@/dashboard/connection/observability";

export function useConnectionSummary(): ConnectionSummary {
  const connection = useRuntimeStore((s) => s.connection);
  const runtime = useRuntimeStore((s) => s.runtime);
  const replay = useRuntimeStore((s) => s.replay);
  const stats = useRuntimeStore((s) => s.stats);
  const lastSequence = useRuntimeStore((s) => s.lastSequence);
  const nowMs = useNowMs();

  return useMemo(() => {
    const metrics = getConnectionMetrics();
    const start = typeof performance !== "undefined" ? performance.now() : Date.now();
    const summary = projectConnection({
      connection,
      runtime,
      replay,
      stats,
      lastSequence,
      nowMs,
      hydrationInFlight: false,
    });
    const end = typeof performance !== "undefined" ? performance.now() : Date.now();
    metrics.recordProjection(end - start);
    return summary;
  }, [connection, runtime, replay, stats, lastSequence, nowMs]);
}
