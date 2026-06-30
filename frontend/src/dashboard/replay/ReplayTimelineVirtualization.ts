/**
 * Marker virtualization helpers.
 *
 * Recordings can carry tens of thousands of markers; rendering one
 * DOM node per marker breaks the frame budget. The helpers here:
 *
 *   * window markers to the visible viewport (cheap predicate, no
 *     allocation when the input is already filtered);
 *   * cap the rendered count per pixel column so a dense burst
 *     collapses into one visible glyph;
 *   * group adjacent markers into clusters when they would otherwise
 *     overlap, so the mini-map / scrubber renders one tinted glyph
 *     for each cluster instead of N stacked ones.
 */

import { sequenceToPixel } from "@/dashboard/replay/ReplayTimelineGeometry";
import type {
  ReplayMarkerSeverity,
  ReplayTimelineMarker,
  ReplayTimelineViewport,
} from "@/dashboard/replay/models/ReplayTimelineModels";

/** One virtualization output entry — either a single marker or a
 *  cluster of overlapping markers. */
export interface ReplayMarkerCluster {
  readonly id: string;
  readonly pixelX: number;
  readonly count: number;
  /** Dominant severity in the cluster — picked by the strictest
   *  level present (critical > warning > info). */
  readonly severity: ReplayMarkerSeverity;
  /** First marker in the cluster — used as the "primary" target for
   *  hover + activation. */
  readonly primary: ReplayTimelineMarker;
  /** All markers in the cluster (only populated when ``count > 1``). */
  readonly members?: readonly ReplayTimelineMarker[];
}

const SEVERITY_RANK: Record<ReplayMarkerSeverity, number> = {
  info: 0,
  warning: 1,
  critical: 2,
};

function dominantSeverity(
  primary: ReplayMarkerSeverity,
  next: ReplayMarkerSeverity,
): ReplayMarkerSeverity {
  return SEVERITY_RANK[next] > SEVERITY_RANK[primary] ? next : primary;
}

/**
 * Window + cluster markers for a given viewport. ``clusterRadiusPx``
 * controls how close two markers can be before they're merged.
 */
export function virtualizeMarkers(
  markers: readonly ReplayTimelineMarker[],
  viewport: ReplayTimelineViewport,
  clusterRadiusPx: number = 4,
): readonly ReplayMarkerCluster[] {
  if (markers.length === 0 || viewport.widthPx <= 0) return [];
  const clusters: ReplayMarkerCluster[] = [];
  let openCluster: {
    primary: ReplayTimelineMarker;
    members: ReplayTimelineMarker[];
    severity: ReplayMarkerSeverity;
    pixelX: number;
  } | null = null;
  for (const marker of markers) {
    if (marker.sequence < viewport.startSequence || marker.sequence > viewport.endSequence) {
      continue;
    }
    const pixelX = sequenceToPixel(marker.sequence, viewport);
    if (openCluster === null) {
      openCluster = {
        primary: marker,
        members: [marker],
        severity: marker.severity,
        pixelX,
      };
      continue;
    }
    if (Math.abs(pixelX - openCluster.pixelX) <= clusterRadiusPx) {
      openCluster.members.push(marker);
      openCluster.severity = dominantSeverity(openCluster.severity, marker.severity);
      continue;
    }
    // Flush the open cluster.
    clusters.push(materialize(openCluster));
    openCluster = {
      primary: marker,
      members: [marker],
      severity: marker.severity,
      pixelX,
    };
  }
  if (openCluster !== null) {
    clusters.push(materialize(openCluster));
  }
  return clusters;
}

function materialize(open: {
  primary: ReplayTimelineMarker;
  members: ReplayTimelineMarker[];
  severity: ReplayMarkerSeverity;
  pixelX: number;
}): ReplayMarkerCluster {
  if (open.members.length === 1) {
    return {
      id: open.primary.id,
      pixelX: open.pixelX,
      count: 1,
      severity: open.severity,
      primary: open.primary,
    };
  }
  return {
    id: `cluster:${open.primary.id}:${open.members.length}`,
    pixelX: open.pixelX,
    count: open.members.length,
    severity: open.severity,
    primary: open.primary,
    members: open.members.slice(),
  };
}

/**
 * Hit-test virtualized clusters against a pointer X coordinate.
 * Returns the closest cluster within ``radiusPx``, or ``null``.
 */
export function pickClusterAt(
  clusters: readonly ReplayMarkerCluster[],
  pixelX: number,
  radiusPx: number = 6,
): ReplayMarkerCluster | null {
  let best: ReplayMarkerCluster | null = null;
  let bestDistance = radiusPx;
  for (const cluster of clusters) {
    const distance = Math.abs(cluster.pixelX - pixelX);
    if (distance <= bestDistance) {
      best = cluster;
      bestDistance = distance;
    }
  }
  return best;
}
