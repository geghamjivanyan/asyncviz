/**
 * Hit-testing + focus utilities for the semaphore panel.
 *
 * Overlay pointer events + panel keyboard navigation both go through
 * here so selection routing converges on the same answer.
 */

import type { MarkerLayout } from "@/dashboard/semaphores/SemaphoreContentionGeometry";
import { pickMarkerAt } from "@/dashboard/semaphores/SemaphoreContentionGeometry";
import type {
  SemaphoreContentionMarker,
  SemaphoreContentionView,
} from "@/dashboard/semaphores/models/SemaphoreContentionModels";

export interface SemaphoreContentionHit {
  semaphoreId: string;
  marker?: SemaphoreContentionMarker;
}

export function hitTestMarkers(
  layouts: ReadonlyArray<MarkerLayout>,
  pointerX: number,
  tolerance = 8,
): SemaphoreContentionHit | null {
  const hit = pickMarkerAt(layouts, pointerX, tolerance);
  if (hit === null) return null;
  return { semaphoreId: hit.marker.semaphoreId, marker: hit.marker };
}

export function neighborSemaphoreId(
  views: ReadonlyArray<SemaphoreContentionView>,
  currentId: string | null,
  direction: 1 | -1,
): string | null {
  if (views.length === 0) return null;
  if (currentId === null) {
    return direction === 1 ? views[0].semaphoreId : views[views.length - 1].semaphoreId;
  }
  const index = views.findIndex((v) => v.semaphoreId === currentId);
  if (index === -1) return views[0].semaphoreId;
  const next = index + direction;
  if (next < 0 || next >= views.length) return currentId;
  return views[next].semaphoreId;
}
