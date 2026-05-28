/**
 * Zustand selector hooks for :class:`ExecutorActivityStore`.
 */

import { useMemo } from "react";
import { useExecutorActivityStore } from "@/dashboard/executors/ExecutorActivityStore";
import { projectExecutorActivity } from "@/dashboard/executors/ExecutorActivityProjection";
import type {
  ExecutorActivityView,
  ExecutorMetricsRecord,
} from "@/dashboard/executors/models/ExecutorActivityModels";

export function useExecutorRecords(): ReadonlyArray<ExecutorMetricsRecord> {
  const recordsById = useExecutorActivityStore((s) => s.recordsById);
  const executorIds = useExecutorActivityStore((s) => s.executorIds);
  return useMemo(
    () => executorIds.map((id) => recordsById[id]).filter(Boolean),
    [recordsById, executorIds],
  );
}

export function useExecutorActivityViews(): ReadonlyArray<ExecutorActivityView> {
  const records = useExecutorRecords();
  return useMemo(
    () => projectExecutorActivity({ records }).views,
    [records],
  );
}

export function useExecutorActivityViewsBySeverity(): ReadonlyArray<ExecutorActivityView> {
  const records = useExecutorRecords();
  return useMemo(
    () => projectExecutorActivity({ records }).bySeverityDescending,
    [records],
  );
}

export function useSelectedExecutorView(): ExecutorActivityView | null {
  const selectedId = useExecutorActivityStore((s) => s.selectedExecutorId);
  const views = useExecutorActivityViewsBySeverity();
  return useMemo(() => {
    if (selectedId === null) return null;
    return views.find((v) => v.executorId === selectedId) ?? null;
  }, [selectedId, views]);
}

export function useExecutorActivitySelfMetrics() {
  return useExecutorActivityStore((s) => s.selfMetrics);
}

export function useExecutorActivityMarkers() {
  return useExecutorActivityStore((s) => s.markers);
}

export function useExecutorActivityStats() {
  return useExecutorActivityStore((s) => s.stats);
}

export function useExecutorActivityStatus() {
  return useExecutorActivityStore((s) => s.status);
}

export function useExecutorActivityErrorMessage() {
  return useExecutorActivityStore((s) => s.errorMessage);
}
