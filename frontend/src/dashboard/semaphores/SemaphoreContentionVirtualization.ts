/**
 * Visible-window virtualization for the semaphore panel + overlay.
 *
 * Same shape as the queue layer — kept in its own module so a future
 * combined contention overlay can opt into either virtualizer.
 */

import type { MarkerLayout } from "@/dashboard/semaphores/SemaphoreContentionGeometry";
import type { SemaphoreContentionView } from "@/dashboard/semaphores/models/SemaphoreContentionModels";

export interface ListVirtualizationInputs {
  views: ReadonlyArray<SemaphoreContentionView>;
  viewportHeight: number;
  rowHeight: number;
  scrollTop: number;
  overscan?: number;
}

export interface ListVirtualizationOutput {
  visible: SemaphoreContentionView[];
  startIndex: number;
  endIndex: number;
  totalHeight: number;
  offsetTop: number;
}

export function virtualizeList(inputs: ListVirtualizationInputs): ListVirtualizationOutput {
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
  maxMarkers?: number;
}

export interface MarkerVirtualizationOutput {
  visible: MarkerLayout[];
  overflow: number;
}

const DEFAULT_MAX_MARKERS = 256;

export function virtualizeMarkers(inputs: MarkerVirtualizationInputs): MarkerVirtualizationOutput {
  const { layouts, maxMarkers = DEFAULT_MAX_MARKERS } = inputs;
  if (layouts.length <= maxMarkers) {
    return { visible: [...layouts], overflow: 0 };
  }
  return {
    visible: layouts.slice(layouts.length - maxMarkers),
    overflow: layouts.length - maxMarkers,
  };
}
