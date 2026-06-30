/**
 * String builders for semaphore-contention accessibility announcements.
 *
 * Pure functions. Components wrap them in ``aria-live`` regions; no
 * DOM imports here.
 */

import type {
  SemaphoreContentionMarker,
  SemaphoreContentionSeverity,
  SemaphoreContentionView,
} from "@/dashboard/semaphores/models/SemaphoreContentionModels";
import { markerLabel, severityLabel } from "@/dashboard/semaphores/SemaphoreContentionSeverity";

/** One-line summary suitable for a card's ``aria-label``. */
export function describeSemaphoreForAccessibility(view: SemaphoreContentionView): string {
  const pieces: string[] = [
    `Semaphore ${view.displayName}`,
    `${severityLabel(view.severity)} contention`,
    `${view.permitsInUse}/${view.initialValue} permits in use`,
  ];
  if (view.waiterCount > 0) {
    pieces.push(`${view.waiterCount} waiter${view.waiterCount === 1 ? "" : "s"}`);
  }
  if (view.saturated) {
    pieces.push("saturated");
  }
  return pieces.join(", ");
}

/** Roll-up summary for the panel's live region. */
export function describeSemaphoreCountsAnnouncement(
  views: ReadonlyArray<SemaphoreContentionView>,
): string {
  if (views.length === 0) return "No semaphores tracked.";
  const buckets: Record<SemaphoreContentionSeverity, number> = {
    calm: 0,
    warning: 0,
    critical: 0,
    saturated: 0,
  };
  for (const view of views) buckets[view.severity] += 1;
  const tally: string[] = [];
  if (buckets.saturated > 0) tally.push(`${buckets.saturated} saturated`);
  if (buckets.critical > 0) tally.push(`${buckets.critical} critical`);
  if (buckets.warning > 0) tally.push(`${buckets.warning} warning`);
  if (buckets.calm > 0) tally.push(`${buckets.calm} calm`);
  return `${views.length} semaphores — ${tally.join(", ")}.`;
}

export function describeSemaphoreFocusAnnouncement(view: SemaphoreContentionView): string {
  return `Focused semaphore ${view.displayName}, ${severityLabel(view.severity)} contention.`;
}

export function describeMarkerAnnouncement(marker: SemaphoreContentionMarker): string {
  return `${markerLabel(marker.kind)} on semaphore ${marker.semaphoreId}: ${marker.label}.`;
}
