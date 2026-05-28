/**
 * Pure helper that snapshots the canonical :class:`TimelineScaleEngine`
 * into an observable :type:`TimelineZoomState`.
 *
 * The controller calls :func:`buildZoomState` after every scale change
 * so subscribers can render the toolbar / a11y companion without
 * re-deriving zoom math themselves.
 */

import type { TimelineScaleEngine } from "@/dashboard/timeline/scaling/TimelineScaleEngine";
import { durationToLevel } from "@/dashboard/timeline/zoom/utils/levelMath";
import type { TimelineZoomState } from "@/dashboard/timeline/zoom/models/TimelineZoomModels";

/** Pure: derive a :type:`TimelineZoomState` from the active engine
 *  state. */
export function buildZoomState(engine: TimelineScaleEngine): TimelineZoomState {
  const scale = engine.currentScale();
  const constraints = engine.currentConstraints();
  const bounds = {
    minDurationSeconds: constraints.minDurationSeconds,
    maxDurationSeconds: constraints.maxDurationSeconds,
  };
  const level = durationToLevel(scale.durationSeconds, bounds);
  return {
    durationSeconds: scale.durationSeconds,
    level,
    atMin: scale.durationSeconds <= constraints.minDurationSeconds * (1 + 1e-9),
    atMax: scale.durationSeconds >= constraints.maxDurationSeconds * (1 - 1e-9),
    minDurationSeconds: constraints.minDurationSeconds,
    maxDurationSeconds: constraints.maxDurationSeconds,
    pixelsPerSecond: scale.pixelsPerSecond,
    scaleKey: scale.key,
  };
}
