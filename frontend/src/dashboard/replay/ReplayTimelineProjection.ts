/**
 * Pure projections that turn replay-store data into render-ready
 * structures (marker placements, bookmark placements, bucket
 * histograms). Render components consume the output of these
 * functions directly without doing geometry themselves.
 */

import { sequenceInViewport, sequenceToPixel } from "@/dashboard/replay/ReplayTimelineGeometry";
import type {
  ReplayBookmark,
  ReplaySessionWindow,
  ReplayTimelineBucket,
  ReplayTimelineMarker,
  ReplayTimelineViewport,
} from "@/dashboard/replay/models/ReplayTimelineModels";

/** A marker prepared for direct DOM/SVG placement. */
export interface ReplayMarkerPlacement {
  readonly marker: ReplayTimelineMarker;
  readonly pixelX: number;
}

/** Project markers onto the current viewport. Off-screen markers
 *  are skipped so the renderer never has to walk dead frames. */
export function projectMarkers(
  markers: readonly ReplayTimelineMarker[],
  viewport: ReplayTimelineViewport,
): readonly ReplayMarkerPlacement[] {
  if (viewport.widthPx <= 0) return [];
  const out: ReplayMarkerPlacement[] = [];
  for (const marker of markers) {
    if (!sequenceInViewport(marker.sequence, viewport)) continue;
    out.push({
      marker,
      pixelX: sequenceToPixel(marker.sequence, viewport),
    });
  }
  return out;
}

/** Bookmark placement — identical shape to marker placement but
 *  rendered with its own styling. */
export interface ReplayBookmarkPlacement {
  readonly bookmark: ReplayBookmark;
  readonly pixelX: number;
}

export function projectBookmarks(
  bookmarks: readonly ReplayBookmark[],
  viewport: ReplayTimelineViewport,
): readonly ReplayBookmarkPlacement[] {
  if (viewport.widthPx <= 0) return [];
  const out: ReplayBookmarkPlacement[] = [];
  for (const bookmark of bookmarks) {
    if (!sequenceInViewport(bookmark.sequence, viewport)) continue;
    out.push({
      bookmark,
      pixelX: sequenceToPixel(bookmark.sequence, viewport),
    });
  }
  return out;
}

/**
 * Bucket markers across the *whole window* (not the viewport) — for
 * the mini-map heatmap. ``bucketCount`` controls horizontal
 * resolution; a typical value is the mini-map width in pixels so
 * each bucket maps to one column.
 */
export function bucketMarkers(
  markers: readonly ReplayTimelineMarker[],
  window: ReplaySessionWindow,
  bucketCount: number,
): readonly ReplayTimelineBucket[] {
  if (bucketCount <= 0) return [];
  const span = Math.max(0, window.maxSequence - window.minSequence);
  if (span === 0) return [];
  const stride = span / bucketCount;
  const buckets: ReplayTimelineBucket[] = [];
  for (let i = 0; i < bucketCount; i += 1) {
    const start = Math.round(window.minSequence + i * stride);
    const end =
      i === bucketCount - 1
        ? window.maxSequence
        : Math.round(window.minSequence + (i + 1) * stride) - 1;
    buckets.push({
      startSequence: start,
      endSequence: end,
      markerCount: 0,
      severityCount: { info: 0, warning: 0, critical: 0 },
    });
  }
  for (const marker of markers) {
    if (marker.sequence < window.minSequence) continue;
    if (marker.sequence > window.maxSequence) continue;
    const relative = marker.sequence - window.minSequence;
    const idx = Math.min(buckets.length - 1, Math.floor(relative / stride));
    const bucket = buckets[idx];
    const severityCounts = { ...bucket.severityCount };
    severityCounts[marker.severity] += 1;
    buckets[idx] = {
      ...bucket,
      markerCount: bucket.markerCount + 1,
      severityCount: severityCounts,
    };
  }
  return buckets;
}

/** Find the marker nearest to a sequence (used for hover / focus). */
export function findNearestMarker(
  markers: readonly ReplayTimelineMarker[],
  sequence: number,
): ReplayTimelineMarker | null {
  if (markers.length === 0) return null;
  let best = markers[0];
  let bestDistance = Math.abs(best.sequence - sequence);
  for (let i = 1; i < markers.length; i += 1) {
    const distance = Math.abs(markers[i].sequence - sequence);
    if (distance < bestDistance) {
      best = markers[i];
      bestDistance = distance;
    }
  }
  return best;
}
