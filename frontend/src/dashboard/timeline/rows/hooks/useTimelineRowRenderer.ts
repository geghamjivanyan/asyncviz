/**
 * React glue for the canonical :class:`TimelineRowRenderer`.
 *
 * Most callers get the row renderer "for free" through
 * :func:`useTimelineRenderer`'s default layer set. This hook is the
 * escape hatch — it constructs a layer instance and registers it with
 * an externally-owned :class:`TimelineRenderer` (e.g. when callers
 * compose the renderer themselves and skip the default layer set).
 */

import { useEffect, useMemo } from "react";
import {
  TimelineRowRenderer,
  type TimelineRowRendererOptions,
} from "@/dashboard/timeline/rows/TimelineRowRenderer";
import type { TimelineRenderer } from "@/dashboard/timeline/rendering/TimelineRenderer";

export interface UseTimelineRowRendererArgs {
  renderer: TimelineRenderer | null;
  options?: TimelineRowRendererOptions;
}

export function useTimelineRowRenderer({
  renderer,
  options,
}: UseTimelineRowRendererArgs): TimelineRowRenderer {
  const layer = useMemo(
    () => new TimelineRowRenderer(options),
    // The layer is constructed once per host — options changes won't
    // recreate it. Callers that need a different layer should swap
    // hosts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  useEffect(() => {
    if (renderer === null) return;
    renderer.addLayer(layer.background);
    renderer.addLayer(layer.foreground);
    return () => {
      renderer.removeLayer(layer.background.id);
      renderer.removeLayer(layer.foreground.id);
    };
  }, [renderer, layer]);

  return layer;
}
