/**
 * Canvas-free renderer surface for the queue pressure overlay.
 *
 * Unlike the timeline, queue-pressure markers don't need GPU-class
 * draw rates — a handful of pointer-event-bearing DOM elements is the
 * better tradeoff (accessibility + tooltip text out of the box).
 *
 * This module is therefore a *projection-driven layout engine* + a
 * tiny imperative shim that any React or canvas overlay can adapt.
 * The :class:`QueuePressureOverlay` component consumes ``layoutFrame``
 * directly to position absolute-positioned markers.
 *
 * The same surface can also be plugged into the timeline's
 * :type:`TimelineLayer` interface — a forthcoming canvas layer can
 * call ``layoutFrame`` then issue draw calls. The split keeps the
 * geometry pure + testable.
 */

import type { MarkerLayoutInputs } from "@/dashboard/queues/QueuePressureGeometry";
import { layoutMarkers } from "@/dashboard/queues/QueuePressureGeometry";
import {
  virtualizeMarkers,
  type MarkerVirtualizationOutput,
} from "@/dashboard/queues/QueuePressureVirtualization";
import type { QueuePressureMarker } from "@/dashboard/queues/models/QueuePressureModels";
import { getQueuePressurePanelMetrics } from "@/dashboard/queues/diagnostics/QueuePressureMetricsCollector";
import { recordQueuePressureTrace } from "@/dashboard/queues/diagnostics/QueuePressureTracing";

export interface QueuePressureFrameInputs extends MarkerLayoutInputs {
  markers: ReadonlyArray<QueuePressureMarker>;
  /** Override marker cap; defaults to the virtualization helper's value. */
  maxMarkers?: number;
}

export interface QueuePressureFrame extends MarkerVirtualizationOutput {
  /** Number of markers that fell within the viewport before culling. */
  windowedMarkerCount: number;
}

/**
 * Deterministic layout pass — pure function of inputs. The caller can
 * memoize on inputs reference equality. Records observability counters
 * + trace entries when active.
 */
export function layoutFrame(inputs: QueuePressureFrameInputs): QueuePressureFrame {
  const layouts = layoutMarkers(inputs.markers, inputs);
  const virtualized = virtualizeMarkers({
    layouts,
    maxMarkers: inputs.maxMarkers,
  });
  getQueuePressurePanelMetrics().recordMarkersRendered(virtualized.visible.length);
  recordQueuePressureTrace({
    kind: "overlay-rendered",
    detail: `visible=${virtualized.visible.length} overflow=${virtualized.overflow}`,
  });
  return { ...virtualized, windowedMarkerCount: layouts.length };
}

/** Identity comparator — useful for React keys on marker layouts. */
export function markerLayoutKey(marker: QueuePressureMarker): string {
  return marker.id;
}
