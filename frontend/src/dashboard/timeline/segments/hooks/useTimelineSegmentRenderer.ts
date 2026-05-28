/**
 * React glue for the canonical :class:`TimelineSegmentRenderer`.
 *
 * The default layer set already includes the segment renderer (added
 * by :func:`useTimelineRenderer`). This hook is the escape hatch —
 * it constructs a fresh renderer + registers it with an
 * externally-owned :class:`TimelineRenderer` (e.g. when callers
 * compose the renderer themselves and skip the default layer set).
 */

import { useEffect, useMemo } from "react";
import {
  TimelineSegmentRenderer,
  type TimelineSegmentRendererOptions,
} from "@/dashboard/timeline/segments/TimelineSegmentRenderer";
import type { TimelineRenderer } from "@/dashboard/timeline/rendering/TimelineRenderer";

export interface UseTimelineSegmentRendererArgs {
  renderer: TimelineRenderer | null;
  options?: TimelineSegmentRendererOptions;
}

export function useTimelineSegmentRenderer({
  renderer,
  options,
}: UseTimelineSegmentRendererArgs): TimelineSegmentRenderer {
  const layer = useMemo(
    () => new TimelineSegmentRenderer(options),
    // Construct once per host — option changes don't recreate it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  useEffect(() => {
    if (renderer === null) return;
    renderer.addLayer(layer);
    return () => {
      renderer.removeLayer(layer.id);
    };
  }, [renderer, layer]);

  return layer;
}
