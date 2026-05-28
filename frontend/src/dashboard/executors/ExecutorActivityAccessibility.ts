/**
 * Pure string builders for executor activity aria-live announcements.
 */

import type {
  ExecutorActivityMarker,
  ExecutorActivitySeverity,
  ExecutorActivityView,
} from "@/dashboard/executors/models/ExecutorActivityModels";
import {
  markerLabel,
  severityLabel,
} from "@/dashboard/executors/ExecutorActivitySeverity";

/** One-line summary suitable for a card's ``aria-label``. */
export function describeExecutorForAccessibility(view: ExecutorActivityView): string {
  const workers = view.maxWorkers !== null
    ? `${view.activeWorkers}/${view.maxWorkers} workers`
    : `${view.activeWorkers} workers`;
  const pieces: string[] = [
    `Executor ${view.displayName}`,
    `${severityLabel(view.severity)} saturation`,
    workers,
  ];
  if (view.backlog > 0) pieces.push(`${view.backlog} backlog`);
  if (view.failures > 0) pieces.push(`${view.failures} failed`);
  if (view.saturated) pieces.push("saturated");
  return pieces.join(", ");
}

/** Roll-up summary for the panel's live region. */
export function describeExecutorCountsAnnouncement(
  views: ReadonlyArray<ExecutorActivityView>,
): string {
  if (views.length === 0) return "No executors tracked.";
  const buckets: Record<ExecutorActivitySeverity, number> = {
    calm: 0, warning: 0, critical: 0, saturated: 0,
  };
  for (const view of views) buckets[view.severity] += 1;
  const tally: string[] = [];
  if (buckets.saturated > 0) tally.push(`${buckets.saturated} saturated`);
  if (buckets.critical > 0) tally.push(`${buckets.critical} critical`);
  if (buckets.warning > 0) tally.push(`${buckets.warning} warning`);
  if (buckets.calm > 0) tally.push(`${buckets.calm} calm`);
  return `${views.length} executors — ${tally.join(", ")}.`;
}

export function describeExecutorFocusAnnouncement(
  view: ExecutorActivityView,
): string {
  return `Focused executor ${view.displayName}, ${severityLabel(view.severity)} saturation.`;
}

export function describeMarkerAnnouncement(
  marker: ExecutorActivityMarker,
): string {
  return `${markerLabel(marker.kind)} on executor ${marker.executorId}: ${marker.label}.`;
}
