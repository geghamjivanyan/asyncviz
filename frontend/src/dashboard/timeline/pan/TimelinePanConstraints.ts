/**
 * Pure helpers that adapt the scale engine's constraints + an
 * optional :type:`PanBounds` into the pan controller's idiom.
 */

import {
  atBoundEdge,
  clampTimeStart,
  wouldExceedBound,
} from "@/dashboard/timeline/pan/utils/panMath";
import {
  UNBOUNDED_PAN,
  type PanBounds,
} from "@/dashboard/timeline/pan/models/TimelinePanModels";

export interface BoundedPanInputs {
  timeStartSeconds: number;
  durationSeconds: number;
  bounds: PanBounds;
}

/** Pure: clamp a candidate ``timeStart`` to the configured bounds. */
export function clampPanTimeStart(
  candidate: number,
  inputs: BoundedPanInputs,
): number {
  return clampTimeStart(
    candidate,
    inputs.durationSeconds,
    inputs.bounds.minTimeSeconds,
    inputs.bounds.maxTimeSeconds,
  );
}

/** Pure: report whether the viewport sits at either bound. */
export function viewportEdgeState(
  inputs: BoundedPanInputs,
): { atMin: boolean; atMax: boolean } {
  return atBoundEdge(
    inputs.timeStartSeconds,
    inputs.durationSeconds,
    inputs.bounds.minTimeSeconds,
    inputs.bounds.maxTimeSeconds,
  );
}

/** Pure: ``true`` when applying ``deltaSeconds`` would push past the
 *  configured bound. */
export function panWouldExceedBound(
  deltaSeconds: number,
  inputs: BoundedPanInputs,
): "min" | "max" | null {
  return wouldExceedBound(
    inputs.timeStartSeconds,
    inputs.durationSeconds,
    deltaSeconds,
    inputs.bounds.minTimeSeconds,
    inputs.bounds.maxTimeSeconds,
  );
}

/** Pure: merge user-supplied bounds with the unbounded default. */
export function mergeBounds(bounds: Partial<PanBounds> | undefined): PanBounds {
  if (!bounds) return UNBOUNDED_PAN;
  return {
    minTimeSeconds: bounds.minTimeSeconds ?? null,
    maxTimeSeconds: bounds.maxTimeSeconds ?? null,
  };
}
