/**
 * Standalone timeline strip rendering recent semaphore-contention
 * markers above the panel.
 *
 * Same shape as :class:`QueuePressureTimeline`. Auto-bounds to the
 * marker buffer's own span when no explicit window is provided.
 */

import { memo, useLayoutEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { SemaphoreContentionOverlay } from "@/dashboard/semaphores/SemaphoreContentionOverlay";
import { layoutFrame } from "@/dashboard/semaphores/SemaphoreContentionRenderer";
import type { SemaphoreContentionMarker } from "@/dashboard/semaphores/models/SemaphoreContentionModels";

export interface SemaphoreContentionTimelineProps {
  markers: ReadonlyArray<SemaphoreContentionMarker>;
  startNs?: number;
  endNs?: number;
  heightPx?: number;
  viewportWidthOverride?: number;
  onActivateMarker?: (markerId: string, semaphoreId: string) => void;
  className?: string;
}

function deriveAutoWindow(
  markers: ReadonlyArray<SemaphoreContentionMarker>,
): { startNs: number; endNs: number } | null {
  if (markers.length === 0) return null;
  let min = markers[0].monotonicNs;
  let max = min;
  for (const marker of markers) {
    if (marker.monotonicNs < min) min = marker.monotonicNs;
    if (marker.monotonicNs > max) max = marker.monotonicNs;
  }
  const padding = max === min ? 1_000_000 : (max - min) * 0.05;
  return { startNs: min - padding, endNs: max + padding };
}

function SemaphoreContentionTimelineImpl({
  markers,
  startNs,
  endNs,
  heightPx = 24,
  viewportWidthOverride,
  onActivateMarker,
  className,
}: SemaphoreContentionTimelineProps): JSX.Element {
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
      data-testid="semaphore-contention-timeline"
      className={cn("semaphore-contention-timeline", className)}
      style={{ height: `${heightPx}px` }}
    >
      <SemaphoreContentionOverlay
        frame={frame}
        heightPx={heightPx}
        onActivate={onActivateMarker}
        hideWhenEmpty
      />
    </div>
  );
}

export const SemaphoreContentionTimeline = memo(SemaphoreContentionTimelineImpl);
