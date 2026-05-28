/**
 * Timeline-relative geometry for semaphore contention markers.
 *
 * Pure math — no DOM, no React. Same coordinate model as the queue
 * overlay (``[startNs, endNs]`` mapped onto a ``viewportWidth`` strip)
 * so a future combined overlay can reuse a single geometry layer.
 */

import type { SemaphoreContentionMarker } from "@/dashboard/semaphores/models/SemaphoreContentionModels";

export interface MarkerLayoutInputs {
  startNs: number;
  endNs: number;
  viewportWidth: number;
  glyphWidth?: number;
}

export interface MarkerLayout {
  marker: SemaphoreContentionMarker;
  x: number;
  left: number;
  width: number;
  clipped: boolean;
}

const DEFAULT_GLYPH_WIDTH = 12;

export function layoutMarker(
  marker: SemaphoreContentionMarker,
  inputs: MarkerLayoutInputs,
): MarkerLayout {
  const { startNs, endNs, viewportWidth, glyphWidth = DEFAULT_GLYPH_WIDTH } = inputs;
  const span = endNs - startNs;
  if (!Number.isFinite(span) || span <= 0 || viewportWidth <= 0) {
    return { marker, x: 0, left: 0, width: glyphWidth, clipped: true };
  }
  const ratio = (marker.monotonicNs - startNs) / span;
  const x = ratio * viewportWidth;
  const left = x - glyphWidth / 2;
  const clipped = left + glyphWidth < 0 || left > viewportWidth;
  return { marker, x, left, width: glyphWidth, clipped };
}

export function layoutMarkers(
  markers: ReadonlyArray<SemaphoreContentionMarker>,
  inputs: MarkerLayoutInputs,
): MarkerLayout[] {
  const out: MarkerLayout[] = [];
  for (const marker of markers) {
    const layout = layoutMarker(marker, inputs);
    if (!layout.clipped) out.push(layout);
  }
  return out;
}

export function pickMarkerAt(
  layouts: ReadonlyArray<MarkerLayout>,
  pointerX: number,
  tolerance = 8,
): MarkerLayout | null {
  let best: MarkerLayout | null = null;
  let bestDistance = Infinity;
  for (const layout of layouts) {
    const distance = Math.abs(layout.x - pointerX);
    if (distance <= tolerance && distance < bestDistance) {
      best = layout;
      bestDistance = distance;
    }
  }
  return best;
}
