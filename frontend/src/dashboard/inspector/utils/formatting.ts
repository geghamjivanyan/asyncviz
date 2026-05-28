/**
 * Pure formatting helpers used by every inspector panel.
 */

import type { TaskLifecycleState } from "@/types/runtime";

/** Pure: human-readable duration string. */
export function formatDuration(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return "—";
  if (seconds < 0) return "—";
  if (seconds < 1e-3) return `${(seconds * 1e6).toFixed(0)}µs`;
  if (seconds < 1) return `${(seconds * 1e3).toFixed(1)}ms`;
  if (seconds < 60) return `${seconds.toFixed(2)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}m${remainder.toFixed(0).padStart(2, "0")}s`;
}

/** Pure: human-readable percentage. ``null`` falls through. */
export function formatPercent(ratio: number | null): string {
  if (ratio === null || !Number.isFinite(ratio)) return "—";
  return `${(ratio * 100).toFixed(0)}%`;
}

/** Pure: wall-time formatter; falls back to seconds when the input
 *  doesn't look like a wall clock (e.g. monotonic times). */
export function formatWallTime(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return "—";
  if (seconds < 1e6) return `${seconds.toFixed(3)}s`;
  const date = new Date(seconds * 1000);
  if (Number.isNaN(date.getTime())) return `${seconds.toFixed(3)}s`;
  return date.toISOString();
}

/** Pure: stringify a lifecycle state with sensible casing. */
export function formatLifecycleState(state: TaskLifecycleState | "unknown"): string {
  switch (state) {
    case "created":
      return "Created";
    case "running":
      return "Running";
    case "waiting":
      return "Waiting";
    case "completed":
      return "Completed";
    case "cancelled":
      return "Cancelled";
    case "failed":
      return "Failed";
    default:
      return "Unknown";
  }
}

/** Pure: render a stable id in the form ``prefix-…-suffix`` so the
 *  inspector header doesn't blow up on long UUIDs. */
export function shortenIdentifier(id: string, prefix = 6, suffix = 4): string {
  if (id.length <= prefix + suffix + 3) return id;
  return `${id.slice(0, prefix)}…${id.slice(-suffix)}`;
}

/** Pure: format a sequence number with a thousands separator so live
 *  values stay readable. */
export function formatSequence(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return value.toLocaleString();
}

/** Pure: severity → intent token. */
export function severityIntent(
  severity: "info" | "warning" | "error" | "critical" | null | undefined,
): "default" | "accent" | "warning" | "danger" {
  switch (severity) {
    case "critical":
    case "error":
      return "danger";
    case "warning":
      return "warning";
    case "info":
      return "accent";
    default:
      return "default";
  }
}
