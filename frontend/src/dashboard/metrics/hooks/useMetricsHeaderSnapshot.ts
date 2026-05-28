/**
 * Top-level selector — pulls the minimal slices from the runtime
 * store, composes them through :func:`projectMetricsHeader`, and
 * returns a stable :type:`MetricsHeaderSnapshot`.
 *
 * Every consumer card reads from this snapshot. The snapshot
 * identity only changes when something visible changes (see
 * ``signature``); React.memo cards short-circuit otherwise.
 */

import { useMemo } from "react";
import { useRuntimeStore } from "@/state/runtime";
import { useEnvelopesPerSecond } from "@/dashboard/metrics/hooks/useEnvelopesPerSecond";
import { useNowMs } from "@/dashboard/metrics/hooks/useNowMs";
import { projectMetricsHeader } from "@/dashboard/metrics/selectors/projectSummaries";
import type { MetricsHeaderSnapshot } from "@/dashboard/metrics/models/summary";
import { getMetricsHeaderMetrics } from "@/dashboard/metrics/observability";

export function useMetricsHeaderSnapshot(): MetricsHeaderSnapshot {
  const connection = useRuntimeStore((s) => s.connection);
  const runtime = useRuntimeStore((s) => s.runtime);
  const replay = useRuntimeStore((s) => s.replay);
  const timeline = useRuntimeStore((s) => s.timeline);
  const warnings = useRuntimeStore((s) => s.warnings);
  const metrics = useRuntimeStore((s) => s.metrics);
  const stats = useRuntimeStore((s) => s.stats);
  const tasksById = useRuntimeStore((s) => s.tasksById);
  const taskIdsByState = useRuntimeStore((s) => s.taskIdsByState);
  const lastSequence = useRuntimeStore((s) => s.lastSequence);

  const nowMs = useNowMs();
  const envelopesPerSecond = useEnvelopesPerSecond();

  return useMemo(() => {
    const observability = getMetricsHeaderMetrics();
    const start = typeof performance !== "undefined" ? performance.now() : Date.now();
    const snapshot = projectMetricsHeader({
      connection,
      runtime,
      replay,
      timeline,
      warnings,
      metrics,
      stats,
      tasksById,
      taskIdsByState,
      lastSequence,
      nowMs,
      envelopesPerSecond,
    });
    const end = typeof performance !== "undefined" ? performance.now() : Date.now();
    observability.recordProjection(end - start);
    return snapshot;
  }, [
    connection,
    runtime,
    replay,
    timeline,
    warnings,
    metrics,
    stats,
    tasksById,
    taskIdsByState,
    lastSequence,
    nowMs,
    envelopesPerSecond,
  ]);
}
