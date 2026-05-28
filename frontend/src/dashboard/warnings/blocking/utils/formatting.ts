/**
 * Display-formatting helpers for blocking-warning views.
 *
 * Kept separate so component tests can spot-check formatting without
 * mounting React. Every helper accepts primitives (no view-model
 * coupling) so they're trivially reusable in future overlays.
 */

import type {
  BlockingGroupSeverity,
  BlockingGroupState,
  BlockingWarningIntent,
} from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import type { Intent } from "@/ui/theme/tokens";

/** Map the panel intent onto the design-token intent. */
export function intentToken(intent: BlockingWarningIntent): Intent {
  switch (intent) {
    case "freeze":
      return "danger";
    case "critical":
      return "danger";
    case "warning":
      return "warning";
    case "resolved":
      return "success";
    case "info":
    default:
      return "default";
  }
}

/** Render a duration in ms with at most one decimal place. */
export function formatDurationMs(durationMs: number): string {
  if (!Number.isFinite(durationMs) || durationMs <= 0) return "0 ms";
  if (durationMs < 1) return `${(durationMs * 1000).toFixed(0)} µs`;
  if (durationMs < 10) return `${durationMs.toFixed(2)} ms`;
  if (durationMs < 1000) return `${durationMs.toFixed(1)} ms`;
  return `${(durationMs / 1000).toFixed(2)} s`;
}

/** Render a lag value in ms. Wraps :func:`formatDurationMs`. */
export function formatLagMs(lagMs: number): string {
  return formatDurationMs(lagMs);
}

/** Render an integer count with thousands separators. */
export function formatCount(count: number): string {
  if (!Number.isFinite(count)) return "—";
  return count.toLocaleString();
}

/** Short label for a state — matches the badge text. */
export function stateBadgeLabel(state: BlockingGroupState): string {
  switch (state) {
    case "opened":
      return "Opened";
    case "escalating":
      return "Escalating";
    case "active":
      return "Active";
    case "recovered":
      return "Recovered";
    case "expired":
      return "Expired";
    default:
      return state;
  }
}

/** Short label for a severity — matches the badge text. */
export function severityBadgeLabel(severity: BlockingGroupSeverity): string {
  switch (severity) {
    case "FREEZE":
      return "Freeze";
    case "CRITICAL":
      return "Critical";
    case "WARNING":
      return "Warning";
    case "NONE":
    default:
      return "Normal";
  }
}

/** Human-friendly "X · Y" badge text for a freeze duration + capture count. */
export function freezeSummaryLabel(durationMs: number, captureCount: number): string {
  const dur = formatDurationMs(durationMs);
  if (captureCount === 0) return dur;
  return `${dur} · ${captureCount} ${captureCount === 1 ? "capture" : "captures"}`;
}
