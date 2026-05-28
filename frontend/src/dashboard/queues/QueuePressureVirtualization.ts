/**
 * Visible-window virtualization for the queue panel + overlay.
 *
 * Two collections need bounding before they reach the DOM:
 *
 *   1. **Queue card list** — sliced by row index to a viewport-sized
 *      window so the panel doesn't render 4000 cards when 4000 queues
 *      are tracked. Returns the visible slice + the total height of the
 *      virtual scrollable area.
 *   2. **Timeline markers** — already culled by the geometry helper for
 *      *off-viewport* markers, but a dense stream can still leave more
 *      visible markers than we want to render in one frame. We cap the
 *      list to ``maxMarkers`` and report the overflow count so the
 *      overlay can surface a "+N more" badge.
 */

import type { MarkerLayout } from "@/dashboard/queues/QueuePressureGeometry";
import type { QueuePressureView } from "@/dashboard/queues/models/QueuePressureModels";

export interface ListVirtualizationInputs {
  views: ReadonlyArray<QueuePressureView>;
  viewportHeight: number;
  rowHeight: number;
  scrollTop: number;
  /** Overscan rows above + below the viewport to soften scroll-edges. */
  overscan?: number;
}

export interface ListVirtualizationOutput {
  visible: QueuePressureView[];
  startIndex: number;
  endIndex: number;
  totalHeight: number;
  offsetTop: number;
}

export function virtualizeList(
  inputs: ListVirtualizationInputs,
): ListVirtualizationOutput {
  const { views, viewportHeight, rowHeight, scrollTop, overscan = 4 } = inputs;
  const total = views.length;
  if (total === 0 || rowHeight <= 0 || viewportHeight <= 0) {
    return { visible: [], startIndex: 0, endIndex: 0, totalHeight: 0, offsetTop: 0 };
  }
  const rawStart = Math.floor(scrollTop / rowHeight);
  const rawEnd = Math.ceil((scrollTop + viewportHeight) / rowHeight);
  const startIndex = Math.max(0, rawStart - overscan);
  const endIndex = Math.min(total, rawEnd + overscan);
  const visible = views.slice(startIndex, endIndex);
  return {
    visible,
    startIndex,
    endIndex,
    totalHeight: total * rowHeight,
    offsetTop: startIndex * rowHeight,
  };
}

export interface MarkerVirtualizationInputs {
  layouts: ReadonlyArray<MarkerLayout>;
  /** Maximum markers retained for this frame. Beyond this the layer
   *  draws an overflow badge instead of cluttering the timeline. */
  maxMarkers?: number;
}

export interface MarkerVirtualizationOutput {
  visible: MarkerLayout[];
  overflow: number;
}

const DEFAULT_MAX_MARKERS = 256;

export function virtualizeMarkers(
  inputs: MarkerVirtualizationInputs,
): MarkerVirtualizationOutput {
  const { layouts, maxMarkers = DEFAULT_MAX_MARKERS } = inputs;
  if (layouts.length <= maxMarkers) {
    return { visible: [...layouts], overflow: 0 };
  }
  // Keep the *most recent* maxMarkers — the overflow comes from the
  // oldest visible markers, which the user can still inspect from the
  // panel list. Recent events are the more actionable signal.
  return {
    visible: layouts.slice(layouts.length - maxMarkers),
    overflow: layouts.length - maxMarkers,
  };
}
