/**
 * Timeline marker overlay.
 *
 * Renders virtualized clusters of markers as small absolutely-
 * positioned glyphs sitting above the scrubber. Hover + click
 * activate seek-to-marker; the focused marker gets a visible focus
 * ring for keyboard users.
 */

import { useEffect, useMemo, type JSX } from "react";
import { describeMarkerForAccessibility } from "@/dashboard/replay/ReplayTimelineAccessibility";
import { recordMarkerRenderPass } from "@/dashboard/replay/diagnostics/ReplayTimelineMetrics";
import {
  useReplayFocusedMarkerId,
  useReplayMarkers,
  useReplayViewport,
  useReplayWindow,
} from "@/dashboard/replay/ReplayTimelineSelectors";
import { useReplayTimelineStore } from "@/dashboard/replay/ReplayTimelineStore";
import {
  pickClusterAt,
  virtualizeMarkers,
  type ReplayMarkerCluster,
} from "@/dashboard/replay/ReplayTimelineVirtualization";
import { seekToMarker } from "@/dashboard/replay/ReplayTimelineSeek";
import type {
  ReplayControlIntent,
  ReplayMarkerSeverity,
  ReplaySessionWindow,
} from "@/dashboard/replay/models/ReplayTimelineModels";

const SEVERITY_CLASS: Record<ReplayMarkerSeverity, string> = {
  info: "bg-blue-400",
  warning: "bg-amber-400",
  critical: "bg-red-500",
};

export interface ReplayTimelineMarkersProps {
  readonly dispatch: (intent: ReplayControlIntent) => void;
  readonly heightPx?: number;
  readonly className?: string;
}

export function ReplayTimelineMarkers({
  dispatch,
  heightPx = 18,
  className,
}: ReplayTimelineMarkersProps): JSX.Element {
  const markers = useReplayMarkers();
  const viewport = useReplayViewport();
  const window = useReplayWindow();
  const focusedId = useReplayFocusedMarkerId();
  const setFocused = useReplayTimelineStore((s) => s.setFocusedMarker);

  const clusters = useMemo(() => virtualizeMarkers(markers, viewport), [markers, viewport]);

  useEffect(() => {
    recordMarkerRenderPass();
  }, [clusters]);

  return (
    <div
      role="list"
      aria-label="Replay markers"
      className={"relative w-full overflow-hidden " + (className ?? "")}
      style={{ height: heightPx }}
      onPointerDown={(event) => {
        const bounds = event.currentTarget.getBoundingClientRect();
        const cluster = pickClusterAt(clusters, event.clientX - bounds.left, 6);
        if (cluster !== null) {
          setFocused(cluster.primary.id);
          dispatch(seekToMarker(cluster.primary));
        }
      }}
    >
      {clusters.map((cluster) => (
        <MarkerGlyph
          key={cluster.id}
          cluster={cluster}
          focused={cluster.primary.id === focusedId}
          window={window}
        />
      ))}
    </div>
  );
}

interface MarkerGlyphProps {
  readonly cluster: ReplayMarkerCluster;
  readonly focused: boolean;
  readonly window: ReplaySessionWindow;
}

function MarkerGlyph({ cluster, focused, window }: MarkerGlyphProps): JSX.Element {
  const ariaLabel = describeMarkerForAccessibility(cluster.primary, window);
  return (
    <div
      role="listitem"
      aria-label={cluster.count > 1 ? `${ariaLabel} (group of ${cluster.count})` : ariaLabel}
      className={
        "absolute top-1/2 -translate-x-1/2 -translate-y-1/2 h-2.5 w-2.5 rounded-full " +
        SEVERITY_CLASS[cluster.severity] +
        (focused ? " ring-2 ring-accent" : "")
      }
      style={{ left: cluster.pixelX }}
    />
  );
}
