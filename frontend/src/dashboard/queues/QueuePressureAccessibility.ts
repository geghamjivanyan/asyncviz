/**
 * String builders for queue-pressure accessibility announcements.
 *
 * Mirrors :mod:`BlockingWarningAccessibility` — pure functions that
 * return announcement strings. Components wrap them in ``aria-live``
 * regions; no DOM imports here.
 */

import type {
  QueuePressureMarker,
  QueuePressureSeverity,
  QueuePressureView,
} from "@/dashboard/queues/models/QueuePressureModels";
import {
  markerLabel,
  severityLabel,
} from "@/dashboard/queues/QueuePressureSeverity";

/** One-line summary suitable for a card's ``aria-label``. */
export function describeQueueForAccessibility(view: QueuePressureView): string {
  const pieces: string[] = [
    `Queue ${view.displayName}`,
    `${severityLabel(view.severity)} pressure`,
    `size ${view.currentSize}${view.maxsize > 0 ? `/${view.maxsize}` : ""}`,
  ];
  if (view.blockedProducers > 0) {
    pieces.push(`${view.blockedProducers} blocked producers`);
  }
  if (view.blockedConsumers > 0) {
    pieces.push(`${view.blockedConsumers} blocked consumers`);
  }
  if (view.saturated) {
    pieces.push("saturated");
  }
  return pieces.join(", ");
}

/**
 * Roll-up summary for the panel's live region. Spoken when the queue
 * set changes severity composition (e.g. a queue escalates to
 * critical, or saturation clears).
 */
export function describeQueueCountsAnnouncement(views: ReadonlyArray<QueuePressureView>): string {
  if (views.length === 0) return "No queues tracked.";
  const buckets: Record<QueuePressureSeverity, number> = {
    calm: 0,
    warning: 0,
    critical: 0,
    saturated: 0,
  };
  for (const view of views) {
    buckets[view.severity] += 1;
  }
  const tally: string[] = [];
  if (buckets.saturated > 0) tally.push(`${buckets.saturated} saturated`);
  if (buckets.critical > 0) tally.push(`${buckets.critical} critical`);
  if (buckets.warning > 0) tally.push(`${buckets.warning} warning`);
  if (buckets.calm > 0) tally.push(`${buckets.calm} calm`);
  return `${views.length} queues — ${tally.join(", ")}.`;
}

/** Focus announcement — emitted when a queue is selected from the list. */
export function describeQueueFocusAnnouncement(view: QueuePressureView): string {
  return `Focused queue ${view.displayName}, ${severityLabel(view.severity)} pressure.`;
}

/** Marker announcement — emitted when a marker is activated via keyboard. */
export function describeMarkerAnnouncement(marker: QueuePressureMarker): string {
  return `${markerLabel(marker.kind)} on queue ${marker.queueId}: ${marker.label}.`;
}
