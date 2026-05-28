/**
 * Pure projection: wire-shape records → view-shape models.
 *
 * Mirrors :mod:`TimelineSegmentProjection` — the renderer + panel both
 * consume the output of this module, never the raw records. Keeping the
 * shape narrow means views don't have to re-derive ``severity`` /
 * ``displayName`` on every render.
 *
 * Memoization is the *caller's* responsibility. The projection itself
 * is deterministic in its inputs so memoizing on ``(record, name)`` is
 * trivial. We don't memoize internally because the hooks layer already
 * does, and double-memoization just chains hash tables for no win.
 */

import type {
  QueueMetricsRecord,
  QueuePressureMarker,
  QueuePressureView,
} from "@/dashboard/queues/models/QueuePressureModels";
import {
  compareSeverityDesc,
  deriveSeverity,
  markerLabel,
} from "@/dashboard/queues/QueuePressureSeverity";

export interface QueuePressureProjectionInputs {
  records: ReadonlyArray<QueueMetricsRecord>;
  /** Optional per-queue display names; falls back to the queue id. */
  displayNames?: Readonly<Record<string, string>>;
}

export interface QueuePressureProjection {
  views: QueuePressureView[];
  bySeverityDescending: QueuePressureView[];
  /** Number of queues with severity ≥ ``warning``. */
  alarmCount: number;
}

export function projectQueuePressure(
  inputs: QueuePressureProjectionInputs,
): QueuePressureProjection {
  const views = inputs.records.map((record) =>
    projectRecord(record, inputs.displayNames?.[record.queue_id]),
  );
  const bySeverityDescending = [...views].sort((a, b) => {
    const sev = compareSeverityDesc(a.severity, b.severity);
    if (sev !== 0) return sev;
    // Tie-breaker: higher pressure score first, then alphabetic for stability.
    if (a.pressureScore !== b.pressureScore) {
      return b.pressureScore - a.pressureScore;
    }
    return a.displayName.localeCompare(b.displayName);
  });
  let alarmCount = 0;
  for (const view of views) {
    if (view.severity !== "calm") alarmCount += 1;
  }
  return { views, bySeverityDescending, alarmCount };
}

/** Project a single record. Exported for tests + reducers. */
export function projectRecord(
  record: QueueMetricsRecord,
  displayName?: string,
): QueuePressureView {
  const severity = deriveSeverity(record.pressure.level, record.pressure.saturated);
  return {
    queueId: record.queue_id,
    queueKind: record.queue_kind,
    maxsize: record.maxsize,
    sequence: record.sequence,
    displayName: displayName ?? record.queue_id,
    severity,
    level: record.pressure.level,
    pressureScore: record.pressure.pressure_score,
    occupancyRatio: record.occupancy.occupancy_ratio,
    currentSize: record.occupancy.current_size,
    peakSize: record.occupancy.peak_size,
    meanOccupancy: record.occupancy.mean_occupancy,
    putRate: record.throughput.put_rate,
    getRate: record.throughput.get_rate,
    putCount: record.throughput.put_count,
    getCount: record.throughput.get_count,
    producerConsumerDelta: record.throughput.producer_consumer_delta,
    blockedProducers: record.contention.blocked_producers,
    blockedConsumers: record.contention.blocked_consumers,
    blockedPutCount: record.contention.blocked_put_count,
    blockedGetCount: record.contention.blocked_get_count,
    cancelledCount: record.throughput.cancelled_count,
    saturated: record.pressure.saturated,
    saturationRatio: record.pressure.saturation_ratio,
    backlogVelocity: record.pressure.backlog_velocity,
    putWaitP95Seconds: record.put_wait.p95_seconds,
    getWaitP95Seconds: record.get_wait.p95_seconds,
    lastObservedMonotonicNs: 0,
  };
}

// ── marker projection ───────────────────────────────────────────────────

export interface MarkerProjectionInputs {
  markers: ReadonlyArray<QueuePressureMarker>;
  /** Only markers within ``[startNs, endNs]`` are returned. */
  startNs?: number;
  endNs?: number;
  /** Cap to keep render budgets predictable on extremely dense streams. */
  limit?: number;
}

/**
 * Slice the marker buffer to the active viewport. Markers arrive in
 * append order; this is an O(N) window filter, not a full scan of the
 * marker store — the caller passes an already-bounded slice.
 */
export function projectMarkersInWindow(
  inputs: MarkerProjectionInputs,
): QueuePressureMarker[] {
  const { markers, startNs, endNs, limit } = inputs;
  if (markers.length === 0) return [];
  const out: QueuePressureMarker[] = [];
  for (const marker of markers) {
    if (startNs !== undefined && marker.monotonicNs < startNs) continue;
    if (endNs !== undefined && marker.monotonicNs > endNs) continue;
    out.push(marker);
    if (limit !== undefined && out.length >= limit) break;
  }
  return out;
}

/** Build a human label for a marker — used by tooltip + sr announcement. */
export function describeMarker(marker: QueuePressureMarker): string {
  const head = markerLabel(marker.kind);
  return marker.detail ? `${head}: ${marker.detail}` : head;
}
