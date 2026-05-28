/**
 * React glue for the canonical :class:`TimelineVirtualizationEngine`.
 *
 * The hook constructs an engine (one per host) and returns it for
 * callers that need to resolve frames on demand. Optional
 * ``liveEngine`` wires the cross-engine coordinator so future
 * invalidation streams flow correctly.
 */

import { useEffect, useMemo } from "react";
import {
  TimelineVirtualizationEngine,
  type TimelineVirtualizationEngineOptions,
} from "@/dashboard/timeline/virtualization/TimelineVirtualizationEngine";
import { bindVirtualizationToLiveEngine } from "@/dashboard/timeline/virtualization/TimelineVirtualizationCoordinator";
import type { CullableRow } from "@/dashboard/timeline/virtualization/TimelineVisibilityCulling";
import type { SpatialIndexable } from "@/dashboard/timeline/virtualization/utils/spatialIndex";
import type { TimelineLiveEngine } from "@/dashboard/timeline/live/TimelineLiveEngine";

export interface UseTimelineVirtualizationArgs<
  TRow extends CullableRow,
  TSegment extends SpatialIndexable,
> {
  options?: TimelineVirtualizationEngineOptions<TRow, TSegment>;
  liveEngine?: TimelineLiveEngine | null;
}

export interface UseTimelineVirtualizationResult<
  TRow extends CullableRow,
  TSegment extends SpatialIndexable,
> {
  engine: TimelineVirtualizationEngine<TRow, TSegment>;
}

export function useTimelineVirtualization<
  TRow extends CullableRow,
  TSegment extends SpatialIndexable,
>(
  args: UseTimelineVirtualizationArgs<TRow, TSegment> = {},
): UseTimelineVirtualizationResult<TRow, TSegment> {
  const engine = useMemo(
    () => new TimelineVirtualizationEngine<TRow, TSegment>(args.options),
    // Construct once per host — option changes don't recreate it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  useEffect(() => {
    if (!args.liveEngine) return;
    const binding = bindVirtualizationToLiveEngine({
      virtualization: engine,
      liveEngine: args.liveEngine,
    });
    return () => binding.unbind();
  }, [engine, args.liveEngine]);

  return { engine };
}
