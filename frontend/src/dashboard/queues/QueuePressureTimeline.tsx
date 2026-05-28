/**
 * Standalone timeline strip rendering recent queue-pressure markers
 * above the queue list.
 *
 * Designed to layer on top of (or alongside) the existing timeline —
 * accepts the timeline's currently-visible monotonic-ns window. When
 * no window is supplied, the component auto-bounds to the marker
 * buffer's own span so the dashboard can render the strip standalone.
 */

import { memo, useMemo, useRef, useState, useLayoutEffect } from "react";
import { cn } from "@/lib/cn";
import { QueuePressureOverlay } from "@/dashboard/queues/QueuePressureOverlay";
import { layoutFrame } from "@/dashboard/queues/QueuePressureRenderer";
import type { QueuePressureMarker } from "@/dashboard/queues/models/QueuePressureModels";

export interface QueuePressureTimelineProps {
  markers: ReadonlyArray<QueuePressureMarker>;
  /** Explicit window. When omitted the component auto-bounds to markers. */
  startNs?: number;
  endNs?: number;
  /** Strip height in CSS pixels. */
  heightPx?: number;
  /** Optional viewport width override (tests / SSR). */
  viewportWidthOverride?: number;
  onActivateMarker?: (markerId: string, queueId: string) => void;
  className?: string;
}

function deriveAutoWindow(
  markers: ReadonlyArray<QueuePressureMarker>,
): { startNs: number; endNs: number } | null {
  if (markers.length === 0) return null;
  let min = markers[0].monotonicNs;
  let max = min;
  for (const marker of markers) {
    if (marker.monotonicNs < min) min = marker.monotonicNs;
    if (marker.monotonicNs > max) max = marker.monotonicNs;
  }
  // Pad both edges so single-marker scenarios still produce a finite span.
  const padding = max === min ? 1_000_000 : (max - min) * 0.05;
  return { startNs: min - padding, endNs: max + padding };
}

function QueuePressureTimelineImpl({
  markers,
  startNs,
  endNs,
  heightPx = 24,
  viewportWidthOverride,
  onActivateMarker,
  className,
}: QueuePressureTimelineProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [measuredWidth, setMeasuredWidth] = useState(viewportWidthOverride ?? 0);

  useLayoutEffect(() => {
    if (viewportWidthOverride !== undefined) {
      setMeasuredWidth(viewportWidthOverride);
      return;
    }
    const node = containerRef.current;
    if (node === null) return;
    setMeasuredWidth(node.clientWidth);
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      if (containerRef.current !== null) {
        setMeasuredWidth(containerRef.current.clientWidth);
      }
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [viewportWidthOverride]);

  const window = useMemo(() => {
    if (startNs !== undefined && endNs !== undefined) {
      return { startNs, endNs };
    }
    return deriveAutoWindow(markers);
  }, [markers, startNs, endNs]);

  const frame = useMemo(() => {
    if (window === null || measuredWidth <= 0) {
      return { visible: [], overflow: 0, windowedMarkerCount: 0 };
    }
    return layoutFrame({
      markers,
      startNs: window.startNs,
      endNs: window.endNs,
      viewportWidth: measuredWidth,
    });
  }, [markers, window, measuredWidth]);

  return (
    <div
      ref={containerRef}
      data-testid="queue-pressure-timeline"
      className={cn("queue-pressure-timeline", className)}
      style={{ height: `${heightPx}px` }}
    >
      <QueuePressureOverlay
        frame={frame}
        heightPx={heightPx}
        onActivate={onActivateMarker}
        hideWhenEmpty
      />
    </div>
  );
}

export const QueuePressureTimeline = memo(QueuePressureTimelineImpl);
