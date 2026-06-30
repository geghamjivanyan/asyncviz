/**
 * Pure projection: runtime ``SemaphoreRecord`` → renderable
 * ``SemaphoreContentionView``.
 *
 * Mirrors the queue layer's projection module — the renderer + panel
 * both consume the output of this module, never the raw record map.
 * Memoization is the caller's job (the selectors hooks do it).
 */

import type {
  SemaphoreContentionMarker,
  SemaphoreContentionView,
  SemaphoreRecord,
} from "@/dashboard/semaphores/models/SemaphoreContentionModels";
import {
  compareSeverityDesc,
  deriveSeverity,
  markerLabel,
  utilizationOf,
} from "@/dashboard/semaphores/SemaphoreContentionSeverity";

export interface SemaphoreContentionProjectionInputs {
  records: ReadonlyArray<SemaphoreRecord>;
  /** Optional per-semaphore name overrides; fall back to ``record.name`` then id. */
  displayNames?: Readonly<Record<string, string>>;
}

export interface SemaphoreContentionProjection {
  views: SemaphoreContentionView[];
  bySeverityDescending: SemaphoreContentionView[];
  /** Number of semaphores with severity ≥ ``warning``. */
  alarmCount: number;
}

export function projectSemaphoreContention(
  inputs: SemaphoreContentionProjectionInputs,
): SemaphoreContentionProjection {
  const views = inputs.records.map((record) =>
    projectRecord(record, inputs.displayNames?.[record.semaphoreId]),
  );
  const bySeverityDescending = [...views].sort((a, b) => {
    const sev = compareSeverityDesc(a.severity, b.severity);
    if (sev !== 0) return sev;
    if (a.utilizationRatio !== b.utilizationRatio) {
      return b.utilizationRatio - a.utilizationRatio;
    }
    return a.displayName.localeCompare(b.displayName);
  });
  let alarmCount = 0;
  for (const view of views) {
    if (view.severity !== "calm") alarmCount += 1;
  }
  return { views, bySeverityDescending, alarmCount };
}

/** Project a single record. Exported for tests. */
export function projectRecord(
  record: SemaphoreRecord,
  displayName?: string,
): SemaphoreContentionView {
  const severity = deriveSeverity({
    currentValue: record.currentValue,
    initialValue: record.initialValue,
    waiterCount: record.waiterCount,
  });
  const utilization = utilizationOf(record.currentValue, record.initialValue);
  const permitsInUse = record.initialValue - (record.currentValue ?? record.initialValue);
  return {
    semaphoreId: record.semaphoreId,
    semaphoreKind: record.semaphoreKind,
    displayName: displayName ?? record.name ?? record.semaphoreId,
    initialValue: record.initialValue,
    boundValue: record.boundValue,
    permitsInUse: Math.max(0, Math.min(record.initialValue, permitsInUse)),
    currentValue: record.currentValue,
    waiterCount: record.waiterCount,
    peakWaiterCount: record.peakWaiterCount,
    utilizationRatio: utilization,
    severity,
    saturated: severity === "saturated",
    acquireCount: record.acquireCount,
    releaseCount: record.releaseCount,
    blockedAcquireCount: record.blockedAcquireCount,
    cancelledWaitCount: record.cancelledWaitCount,
    meanWaitSeconds: record.meanWaitSeconds,
    maxWaitSeconds: record.maxWaitSeconds,
    sequence: record.sequence,
  };
}

// ── marker projection ───────────────────────────────────────────────────

export interface MarkerProjectionInputs {
  markers: ReadonlyArray<SemaphoreContentionMarker>;
  startNs?: number;
  endNs?: number;
  limit?: number;
}

export function projectMarkersInWindow(
  inputs: MarkerProjectionInputs,
): SemaphoreContentionMarker[] {
  const { markers, startNs, endNs, limit } = inputs;
  if (markers.length === 0) return [];
  const out: SemaphoreContentionMarker[] = [];
  for (const marker of markers) {
    if (startNs !== undefined && marker.monotonicNs < startNs) continue;
    if (endNs !== undefined && marker.monotonicNs > endNs) continue;
    out.push(marker);
    if (limit !== undefined && out.length >= limit) break;
  }
  return out;
}

export function describeMarker(marker: SemaphoreContentionMarker): string {
  const head = markerLabel(marker.kind);
  return marker.detail ? `${head}: ${marker.detail}` : head;
}
