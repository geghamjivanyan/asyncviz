/**
 * Timeline-relative geometry for queue pressure markers.
 *
 * Pure math — no DOM, no React. The renderer overlay reads this to
 * place markers; tests exercise the same functions directly.
 *
 * Coordinate model mirrors the existing timeline:
 *
 *   * The timeline maps the monotonic-ns range ``[startNs, endNs]``
 *     onto a horizontal viewport of width ``viewportWidth`` (in CSS
 *     pixels). A marker at ``markerNs`` lands at:
 *
 *         x = ((markerNs - startNs) / (endNs - startNs)) * viewportWidth
 *
 *   * Marker glyph width is fixed (no time extent) so the helper just
 *     centers the glyph on its anchor x. Anti-aliasing is achieved by
 *     rounding to the nearest half-pixel on the *caller* side; this
 *     module returns subpixel-accurate floats.
 */

import type { QueuePressureMarker } from "@/dashboard/queues/models/QueuePressureModels";

export interface MarkerLayoutInputs {
  startNs: number;
  endNs: number;
  viewportWidth: number;
  /** Glyph width in CSS pixels. Markers narrower than this collide
   *  visually — set it to whatever the renderer draws. */
  glyphWidth?: number;
}

export interface MarkerLayout {
  marker: QueuePressureMarker;
  /** Center x of the glyph, in CSS pixels relative to the viewport origin. */
  x: number;
  /** Left edge of the glyph, useful for absolute positioning. */
  left: number;
  width: number;
  /** ``true`` when the marker is fully outside the viewport. The caller
   *  can use this to skip the render without re-checking math. */
  clipped: boolean;
}

const DEFAULT_GLYPH_WIDTH = 12;

export function layoutMarker(
  marker: QueuePressureMarker,
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
  markers: ReadonlyArray<QueuePressureMarker>,
  inputs: MarkerLayoutInputs,
): MarkerLayout[] {
  const out: MarkerLayout[] = [];
  for (const marker of markers) {
    const layout = layoutMarker(marker, inputs);
    if (!layout.clipped) out.push(layout);
  }
  return out;
}

/**
 * Stable hit-testing — given a pointer x relative to the viewport
 * origin, return the layout closest to the pointer within ``tolerance``
 * pixels. Returns ``null`` when no marker is within range.
 *
 * O(N) but bounded by the visible-marker count after layout culling,
 * which the virtualization layer caps anyway.
 */
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
