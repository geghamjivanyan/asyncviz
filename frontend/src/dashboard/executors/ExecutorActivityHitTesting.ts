/**
 * Pointer + keyboard hit-testing for the executor activity panel.
 */

import type { MarkerLayout } from "@/dashboard/executors/ExecutorActivityGeometry";
import { pickMarkerAt } from "@/dashboard/executors/ExecutorActivityGeometry";
import type {
  ExecutorActivityMarker,
  ExecutorActivityView,
} from "@/dashboard/executors/models/ExecutorActivityModels";

export interface ExecutorActivityHit {
  executorId: string;
  marker?: ExecutorActivityMarker;
}

export function hitTestMarkers(
  layouts: ReadonlyArray<MarkerLayout>,
  pointerX: number,
  tolerance = 8,
): ExecutorActivityHit | null {
  const hit = pickMarkerAt(layouts, pointerX, tolerance);
  if (hit === null) return null;
  return { executorId: hit.marker.executorId, marker: hit.marker };
}

export function neighborExecutorId(
  views: ReadonlyArray<ExecutorActivityView>,
  currentId: string | null,
  direction: 1 | -1,
): string | null {
  if (views.length === 0) return null;
  if (currentId === null) {
    return direction === 1 ? views[0].executorId : views[views.length - 1].executorId;
  }
  const idx = views.findIndex((v) => v.executorId === currentId);
  if (idx === -1) return views[0].executorId;
  const next = idx + direction;
  if (next < 0 || next >= views.length) return currentId;
  return views[next].executorId;
}
