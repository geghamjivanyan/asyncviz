/**
 * Hit-testing + focus utilities for the queue panel.
 *
 * The overlay's pointer events drive selection through these
 * functions so the renderer, the keyboard navigation in the panel, and
 * the inspector reveal action all converge on the same "which queue
 * was activated" answer.
 */

import type { MarkerLayout } from "@/dashboard/queues/QueuePressureGeometry";
import { pickMarkerAt } from "@/dashboard/queues/QueuePressureGeometry";
import type {
  QueuePressureMarker,
  QueuePressureView,
} from "@/dashboard/queues/models/QueuePressureModels";

export interface QueuePressureHit {
  queueId: string;
  marker?: QueuePressureMarker;
}

/** Marker-first hit-test: return the marker under the pointer, else null. */
export function hitTestMarkers(
  layouts: ReadonlyArray<MarkerLayout>,
  pointerX: number,
  tolerance = 8,
): QueuePressureHit | null {
  const hit = pickMarkerAt(layouts, pointerX, tolerance);
  if (hit === null) return null;
  return { queueId: hit.marker.queueId, marker: hit.marker };
}

/**
 * Resolve "next queue" / "previous queue" for keyboard navigation. The
 * panel uses arrow keys to step through ``views`` in display order so
 * selection respects the user's sort.
 */
export function neighborQueueId(
  views: ReadonlyArray<QueuePressureView>,
  currentId: string | null,
  direction: 1 | -1,
): string | null {
  if (views.length === 0) return null;
  if (currentId === null) {
    return direction === 1 ? views[0].queueId : views[views.length - 1].queueId;
  }
  const index = views.findIndex((v) => v.queueId === currentId);
  if (index === -1) return views[0].queueId;
  const next = index + direction;
  if (next < 0 || next >= views.length) return currentId;
  return views[next].queueId;
}
