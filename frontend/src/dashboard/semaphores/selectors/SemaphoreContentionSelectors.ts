/**
 * Zustand selector hooks for :class:`SemaphoreContentionStore`.
 *
 * Each hook subscribes to one slice so consumers don't re-render on
 * unrelated state changes. Derived data flows through the projection
 * layer with ``useMemo`` at the call site.
 */

import { useMemo } from "react";
import { useSemaphoreContentionStore } from "@/dashboard/semaphores/SemaphoreContentionStore";
import { projectSemaphoreContention } from "@/dashboard/semaphores/SemaphoreContentionProjection";
import type {
  SemaphoreContentionView,
  SemaphoreRecord,
} from "@/dashboard/semaphores/models/SemaphoreContentionModels";

export function useSemaphoreRecords(): ReadonlyArray<SemaphoreRecord> {
  const recordsById = useSemaphoreContentionStore((s) => s.recordsById);
  const semaphoreIds = useSemaphoreContentionStore((s) => s.semaphoreIds);
  return useMemo(
    () => semaphoreIds.map((id) => recordsById[id]).filter(Boolean),
    [recordsById, semaphoreIds],
  );
}

export function useSemaphoreContentionViews(): ReadonlyArray<SemaphoreContentionView> {
  const records = useSemaphoreRecords();
  return useMemo(() => projectSemaphoreContention({ records }).views, [records]);
}

export function useSemaphoreContentionViewsBySeverity(): ReadonlyArray<SemaphoreContentionView> {
  const records = useSemaphoreRecords();
  return useMemo(() => projectSemaphoreContention({ records }).bySeverityDescending, [records]);
}

export function useSelectedSemaphoreView(): SemaphoreContentionView | null {
  const selectedId = useSemaphoreContentionStore((s) => s.selectedSemaphoreId);
  const views = useSemaphoreContentionViewsBySeverity();
  return useMemo(() => {
    if (selectedId === null) return null;
    return views.find((v) => v.semaphoreId === selectedId) ?? null;
  }, [selectedId, views]);
}

export function useSemaphoreContentionSelfMetrics() {
  return useSemaphoreContentionStore((s) => s.selfMetrics);
}

export function useSemaphoreContentionMarkers() {
  return useSemaphoreContentionStore((s) => s.markers);
}

export function useSemaphoreContentionStats() {
  return useSemaphoreContentionStore((s) => s.stats);
}

export function useSemaphoreContentionStatus() {
  return useSemaphoreContentionStore((s) => s.status);
}

export function useSemaphoreContentionErrorMessage() {
  return useSemaphoreContentionStore((s) => s.errorMessage);
}
