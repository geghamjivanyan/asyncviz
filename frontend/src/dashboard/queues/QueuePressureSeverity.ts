/**
 * Severity → display mapping for the queue pressure visualization.
 *
 * Centralized so the panel, cards, overlay markers, accessibility
 * helpers, and tests all read from one source of truth. Colors are
 * design tokens declared as CSS custom properties on
 * ``data-severity`` attributes — change the token, every surface
 * updates.
 */

import type {
  QueuePressureLevel,
  QueuePressureMarkerKind,
  QueuePressureSeverity,
} from "@/dashboard/queues/models/QueuePressureModels";

/** Numeric rank — higher = worse. Used by sort helpers + accessibility. */
export const SEVERITY_RANK: Record<QueuePressureSeverity, number> = {
  calm: 0,
  warning: 1,
  critical: 2,
  saturated: 3,
};

const SEVERITY_LABELS: Record<QueuePressureSeverity, string> = {
  calm: "Calm",
  warning: "Warning",
  critical: "Critical",
  saturated: "Saturated",
};

export function severityLabel(severity: QueuePressureSeverity): string {
  return SEVERITY_LABELS[severity];
}

/**
 * Derive the renderable severity from the backend pressure level + the
 * sticky saturation bit. Saturation outranks the pressure score because
 * a queue at ≥0.9 occupancy is the most operationally urgent signal,
 * even if the composite score is technically still "warning".
 */
export function deriveSeverity(
  level: QueuePressureLevel,
  saturated: boolean,
): QueuePressureSeverity {
  if (saturated) return "saturated";
  return level;
}

/** Stable severity ordering for sorts (``critical`` before ``warning``). */
export function compareSeverityDesc(a: QueuePressureSeverity, b: QueuePressureSeverity): number {
  return SEVERITY_RANK[b] - SEVERITY_RANK[a];
}

/**
 * Marker-kind label — the overlay tooltip + screen-reader announcement
 * both pull from here so the wording stays consistent.
 */
const MARKER_LABELS: Record<QueuePressureMarkerKind, string> = {
  "pressure-change": "Pressure change",
  contention: "Contention",
  saturation: "Saturation",
};

export function markerLabel(kind: QueuePressureMarkerKind): string {
  return MARKER_LABELS[kind];
}
