/**
 * Pure helper that snapshots the canonical :class:`TimelineScaleEngine`
 * + the active drag-state into a :type:`TimelinePanState`.
 *
 * The controller already does this internally; the helper exists so
 * external consumers (toolbar previews, debugger overlays) can build
 * the same shape without subscribing to the controller.
 */

import type { TimelineScaleEngine } from "@/dashboard/timeline/scaling/TimelineScaleEngine";
import {
  mergeBounds,
  viewportEdgeState,
} from "@/dashboard/timeline/pan/TimelinePanConstraints";
import type {
  PanBounds,
  TimelinePanState,
} from "@/dashboard/timeline/pan/models/TimelinePanModels";

/** Pure: derive a :type:`TimelinePanState` from the engine + bounds. */
export function buildPanState(
  engine: TimelineScaleEngine,
  bounds: Partial<PanBounds> | undefined = undefined,
  dragging = false,
): TimelinePanState {
  const scale = engine.currentScale();
  const resolved = mergeBounds(bounds);
  const edges = viewportEdgeState({
    timeStartSeconds: scale.timeStart,
    durationSeconds: scale.durationSeconds,
    bounds: resolved,
  });
  return {
    timeStartSeconds: scale.timeStart,
    timeEndSeconds: scale.timeEnd,
    durationSeconds: scale.durationSeconds,
    pixelsPerSecond: scale.pixelsPerSecond,
    dragging,
    atMinTime: edges.atMin,
    atMaxTime: edges.atMax,
    minTimeSeconds: resolved.minTimeSeconds,
    maxTimeSeconds: resolved.maxTimeSeconds,
    scaleKey: scale.key,
  };
}
