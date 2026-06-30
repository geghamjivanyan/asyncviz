/**
 * Severity → display mapping for the semaphore contention visualization.
 *
 * Centralized so the panel, cards, overlay markers, accessibility
 * helpers, and tests all read from one source of truth.
 *
 * Severity is *derived* from runtime state — there's no single "level"
 * field on the wire. The rules:
 *
 *   * ``saturated`` — every permit issued + at least one waiter parked
 *     (the queue analogue of "queue full").
 *   * ``critical`` — utilization ≥ 0.85 OR waiter_count ≥ 2 (multiple
 *     producers waiting on a single resource).
 *   * ``warning`` — utilization ≥ 0.6 OR at least one blocked waiter.
 *   * ``calm`` — everything else.
 *
 * Thresholds are intentionally fixed: a configurable threshold model
 * lands in the metrics-engine task (mirrors what Queue did) once it's
 * wired up.
 */

import type {
  SemaphoreContentionSeverity,
  SemaphoreMarkerKind,
} from "@/dashboard/semaphores/models/SemaphoreContentionModels";

export const SEVERITY_RANK: Record<SemaphoreContentionSeverity, number> = {
  calm: 0,
  warning: 1,
  critical: 2,
  saturated: 3,
};

const SEVERITY_LABELS: Record<SemaphoreContentionSeverity, string> = {
  calm: "Calm",
  warning: "Warning",
  critical: "Critical",
  saturated: "Saturated",
};

export function severityLabel(severity: SemaphoreContentionSeverity): string {
  return SEVERITY_LABELS[severity];
}

export const WARNING_UTILIZATION_THRESHOLD = 0.6;
export const CRITICAL_UTILIZATION_THRESHOLD = 0.85;
export const CRITICAL_WAITER_THRESHOLD = 2;

export interface SeverityInputs {
  currentValue: number | null;
  initialValue: number;
  waiterCount: number;
}

/**
 * Derive the renderable severity from runtime state.
 *
 * Saturated outranks "critical-by-score" because zero permits + parked
 * waiters is the most actionable signal — operators want to see it
 * even if the composite utilization score is otherwise unremarkable.
 */
export function deriveSeverity(inputs: SeverityInputs): SemaphoreContentionSeverity {
  const { currentValue, initialValue, waiterCount } = inputs;
  if (waiterCount > 0 && (currentValue === null || currentValue <= 0)) {
    return "saturated";
  }
  const utilization = utilizationOf(currentValue, initialValue);
  if (utilization >= CRITICAL_UTILIZATION_THRESHOLD || waiterCount >= CRITICAL_WAITER_THRESHOLD) {
    return "critical";
  }
  if (utilization >= WARNING_UTILIZATION_THRESHOLD || waiterCount >= 1) {
    return "warning";
  }
  return "calm";
}

/** Compute utilization ratio in ``[0, 1]``. ``null`` current = 0. */
export function utilizationOf(currentValue: number | null, initialValue: number): number {
  if (initialValue <= 0) return 0;
  const used = initialValue - (currentValue ?? initialValue);
  return Math.max(0, Math.min(1, used / initialValue));
}

/** Stable severity ordering for sorts (``saturated`` first). */
export function compareSeverityDesc(
  a: SemaphoreContentionSeverity,
  b: SemaphoreContentionSeverity,
): number {
  return SEVERITY_RANK[b] - SEVERITY_RANK[a];
}

const MARKER_LABELS: Record<SemaphoreMarkerKind, string> = {
  contention: "Contention",
  saturation: "Saturation",
  "wait-cancelled": "Wait cancelled",
};

export function markerLabel(kind: SemaphoreMarkerKind): string {
  return MARKER_LABELS[kind];
}
