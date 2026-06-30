/**
 * Severity → display mapping for the executor activity visualization.
 *
 * Severity derives from the backend ``saturation_level`` plus a
 * "saturated" escalation when ``utilization_ratio == 1.0`` AND
 * ``backlog > 0`` (every worker busy + items still queued). Saturated
 * outranks the level-based critical because it's the most actionable
 * signal — operators want to see it even if the composite score is
 * technically still "warning".
 */

import type {
  ExecutorActivitySeverity,
  ExecutorMarkerKind,
  ExecutorSaturationLevel,
} from "@/dashboard/executors/models/ExecutorActivityModels";

export const SEVERITY_RANK: Record<ExecutorActivitySeverity, number> = {
  calm: 0,
  warning: 1,
  critical: 2,
  saturated: 3,
};

const SEVERITY_LABELS: Record<ExecutorActivitySeverity, string> = {
  calm: "Calm",
  warning: "Warning",
  critical: "Critical",
  saturated: "Saturated",
};

export function severityLabel(severity: ExecutorActivitySeverity): string {
  return SEVERITY_LABELS[severity];
}

export interface SeverityInputs {
  level: ExecutorSaturationLevel;
  utilizationRatio: number;
  backlog: number;
}

export function deriveSeverity(inputs: SeverityInputs): ExecutorActivitySeverity {
  if (inputs.utilizationRatio >= 1.0 && inputs.backlog > 0) {
    return "saturated";
  }
  return inputs.level;
}

export function compareSeverityDesc(
  a: ExecutorActivitySeverity,
  b: ExecutorActivitySeverity,
): number {
  return SEVERITY_RANK[b] - SEVERITY_RANK[a];
}

const MARKER_LABELS: Record<ExecutorMarkerKind, string> = {
  "saturation-changed": "Saturation",
  contention: "Contention",
  "latency-spike": "Latency spike",
};

export function markerLabel(kind: ExecutorMarkerKind): string {
  return MARKER_LABELS[kind];
}
