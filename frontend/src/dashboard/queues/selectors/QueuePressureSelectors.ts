/**
 * Zustand selector hooks for :class:`QueuePressureStore`.
 *
 * Kept narrow: each hook subscribes to one slice so consumers
 * don't re-render on unrelated state changes. Consumers compose
 * derived data via the projection layer (memoized at the call site).
 */

import { useMemo } from "react";
import { useQueuePressureStore } from "@/dashboard/queues/QueuePressureStore";
import { projectQueuePressure } from "@/dashboard/queues/QueuePressureProjection";
import type {
  QueueMetricsRecord,
  QueuePressureView,
} from "@/dashboard/queues/models/QueuePressureModels";

export function useQueueRecords(): ReadonlyArray<QueueMetricsRecord> {
  const recordsById = useQueuePressureStore((s) => s.recordsById);
  const queueIds = useQueuePressureStore((s) => s.queueIds);
  return useMemo(
    () => queueIds.map((id) => recordsById[id]).filter(Boolean),
    [recordsById, queueIds],
  );
}

export function useQueuePressureViews(): ReadonlyArray<QueuePressureView> {
  const records = useQueueRecords();
  return useMemo(() => projectQueuePressure({ records }).views, [records]);
}

export function useQueuePressureViewsBySeverity(): ReadonlyArray<QueuePressureView> {
  const records = useQueueRecords();
  return useMemo(() => projectQueuePressure({ records }).bySeverityDescending, [records]);
}

export function useSelectedQueueView(): QueuePressureView | null {
  const selectedId = useQueuePressureStore((s) => s.selectedQueueId);
  const views = useQueuePressureViewsBySeverity();
  return useMemo(() => {
    if (selectedId === null) return null;
    return views.find((v) => v.queueId === selectedId) ?? null;
  }, [selectedId, views]);
}

export function useQueuePressureSelfMetrics() {
  return useQueuePressureStore((s) => s.selfMetrics);
}

export function useQueuePressureMarkers() {
  return useQueuePressureStore((s) => s.markers);
}

export function useQueuePressureStats() {
  return useQueuePressureStore((s) => s.stats);
}

export function useQueuePressureStatus() {
  return useQueuePressureStore((s) => s.status);
}

export function useQueuePressureErrorMessage() {
  return useQueuePressureStore((s) => s.errorMessage);
}
