/**
 * Mini-map (overview) strip.
 *
 * Renders the *whole recording* in a small horizontal area,
 * bucketing markers into pixel-wide columns so the strip stays
 * legible even with tens of thousands of markers.
 */

import { useEffect, useMemo, useRef, useState, type JSX } from "react";
import {
  bucketMarkers,
} from "@/dashboard/replay/ReplayTimelineProjection";
import {
  recordBucketRenderPass,
} from "@/dashboard/replay/diagnostics/ReplayTimelineMetrics";
import {
  useReplayMarkers,
  useReplayPlayback,
  useReplayWindow,
} from "@/dashboard/replay/ReplayTimelineSelectors";
import { seekFromFraction } from "@/dashboard/replay/ReplayTimelineSeek";
import {
  sequenceToFraction,
} from "@/dashboard/replay/ReplayTimelineGeometry";
import type {
  ReplayControlIntent,
  ReplayMarkerSeverity,
} from "@/dashboard/replay/models/ReplayTimelineModels";

const SEVERITY_COLOR: Record<ReplayMarkerSeverity, string> = {
  info: "#60a5fa",
  warning: "#f59e0b",
  critical: "#ef4444",
};

export interface ReplayTimelineMiniMapProps {
  readonly dispatch: (intent: ReplayControlIntent) => void;
  readonly heightPx?: number;
  readonly className?: string;
}

export function ReplayTimelineMiniMap({
  dispatch,
  heightPx = 24,
  className,
}: ReplayTimelineMiniMapProps): JSX.Element {
  const markers = useReplayMarkers();
  const window = useReplayWindow();
  const playback = useReplayPlayback();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return undefined;
    setWidth(node.getBoundingClientRect().width);
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      setWidth(entry.contentRect.width);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const buckets = useMemo(() => {
    if (width <= 0) return [];
    return bucketMarkers(markers, window, Math.max(1, Math.floor(width)));
  }, [markers, window, width]);

  useEffect(() => {
    recordBucketRenderPass();
  }, [buckets]);

  const playheadFraction = sequenceToFraction(playback.lastSequence, window);

  return (
    <div
      ref={containerRef}
      role="region"
      aria-label="Replay minimap"
      className={
        "relative w-full cursor-pointer rounded border border-border bg-surfaceMuted " +
        (className ?? "")
      }
      style={{ height: heightPx }}
      onPointerDown={(event) => {
        const bounds = event.currentTarget.getBoundingClientRect();
        const fraction = bounds.width > 0
          ? Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width))
          : 0;
        dispatch(seekFromFraction(fraction, window));
      }}
    >
      <svg
        aria-hidden
        className="absolute inset-0 h-full w-full"
        viewBox={`0 0 ${Math.max(1, width)} ${heightPx}`}
        preserveAspectRatio="none"
      >
        {buckets.map((bucket, idx) => {
          const total = bucket.markerCount;
          if (total === 0) return null;
          const severity: ReplayMarkerSeverity = bucket.severityCount.critical
            ? "critical"
            : bucket.severityCount.warning
              ? "warning"
              : "info";
          const ratio = Math.min(1, total / 32);
          const barHeight = ratio * heightPx;
          return (
            <rect
              key={`${bucket.startSequence}-${bucket.endSequence}`}
              x={idx}
              y={heightPx - barHeight}
              width={1}
              height={barHeight}
              fill={SEVERITY_COLOR[severity]}
            />
          );
        })}
      </svg>
      <div
        aria-hidden
        className="absolute inset-y-0 w-px bg-accent"
        style={{ left: `${playheadFraction * 100}%` }}
      />
    </div>
  );
}
