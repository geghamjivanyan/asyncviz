/**
 * Pure layout-frame builder for the semaphore contention overlay.
 *
 * Single function (``layoutFrame``) that the overlay component, the
 * Diagnostics page, and a future combined-contention canvas layer can
 * all consume. No React, no DOM — geometry only.
 */

import type { MarkerLayoutInputs } from "@/dashboard/semaphores/SemaphoreContentionGeometry";
import { layoutMarkers } from "@/dashboard/semaphores/SemaphoreContentionGeometry";
import {
  virtualizeMarkers,
  type MarkerVirtualizationOutput,
} from "@/dashboard/semaphores/SemaphoreContentionVirtualization";
import type { SemaphoreContentionMarker } from "@/dashboard/semaphores/models/SemaphoreContentionModels";
import { getSemaphoreContentionPanelMetrics } from "@/dashboard/semaphores/diagnostics/SemaphoreContentionMetricsCollector";
import { recordSemaphoreContentionTrace } from "@/dashboard/semaphores/diagnostics/SemaphoreContentionTracing";

export interface SemaphoreContentionFrameInputs extends MarkerLayoutInputs {
  markers: ReadonlyArray<SemaphoreContentionMarker>;
  maxMarkers?: number;
}

export interface SemaphoreContentionFrame extends MarkerVirtualizationOutput {
  windowedMarkerCount: number;
}

export function layoutFrame(
  inputs: SemaphoreContentionFrameInputs,
): SemaphoreContentionFrame {
  const layouts = layoutMarkers(inputs.markers, inputs);
  const virtualized = virtualizeMarkers({
    layouts,
    maxMarkers: inputs.maxMarkers,
  });
  getSemaphoreContentionPanelMetrics().recordMarkersRendered(virtualized.visible.length);
  recordSemaphoreContentionTrace({
    kind: "overlay-rendered",
    detail: `visible=${virtualized.visible.length} overflow=${virtualized.overflow}`,
  });
  return { ...virtualized, windowedMarkerCount: layouts.length };
}

export function markerLayoutKey(marker: SemaphoreContentionMarker): string {
  return marker.id;
}
