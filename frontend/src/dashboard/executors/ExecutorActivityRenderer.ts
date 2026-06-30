/**
 * Pure layout-frame builder for the executor activity overlay.
 */

import type { MarkerLayoutInputs } from "@/dashboard/executors/ExecutorActivityGeometry";
import { layoutMarkers } from "@/dashboard/executors/ExecutorActivityGeometry";
import {
  virtualizeMarkers,
  type MarkerVirtualizationOutput,
} from "@/dashboard/executors/ExecutorActivityVirtualization";
import type { ExecutorActivityMarker } from "@/dashboard/executors/models/ExecutorActivityModels";
import { getExecutorActivityPanelMetrics } from "@/dashboard/executors/diagnostics/ExecutorActivityMetricsCollector";
import { recordExecutorActivityTrace } from "@/dashboard/executors/diagnostics/ExecutorActivityTracing";

export interface ExecutorActivityFrameInputs extends MarkerLayoutInputs {
  markers: ReadonlyArray<ExecutorActivityMarker>;
  maxMarkers?: number;
}

export interface ExecutorActivityFrame extends MarkerVirtualizationOutput {
  windowedMarkerCount: number;
}

export function layoutFrame(inputs: ExecutorActivityFrameInputs): ExecutorActivityFrame {
  const layouts = layoutMarkers(inputs.markers, inputs);
  const virtualized = virtualizeMarkers({
    layouts,
    maxMarkers: inputs.maxMarkers,
  });
  getExecutorActivityPanelMetrics().recordMarkersRendered(virtualized.visible.length);
  recordExecutorActivityTrace({
    kind: "overlay-rendered",
    detail: `visible=${virtualized.visible.length} overflow=${virtualized.overflow}`,
  });
  return { ...virtualized, windowedMarkerCount: layouts.length };
}

export function markerLayoutKey(marker: ExecutorActivityMarker): string {
  return marker.id;
}
