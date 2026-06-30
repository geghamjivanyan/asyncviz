/**
 * Pure mapper from canonical input events to zoom controller calls.
 *
 * The mapper is intentionally tiny — every dispatch is a one-line
 * delegation. Keeping it separate from the controller means the
 * controller stays unit-testable without DOM events and the
 * mapper stays unit-testable without the controller.
 */

import type { TimelineZoomController } from "@/dashboard/timeline/zoom/TimelineZoomController";
import {
  cursorAnchor,
  xAnchor,
  type AnchorResolveContext,
} from "@/dashboard/timeline/zoom/TimelineZoomAnchoring";
import type { WheelGestureInput } from "@/dashboard/timeline/zoom/TimelineZoomGestures";
import type { ZoomAnchor } from "@/dashboard/timeline/zoom/models/TimelineZoomModels";

export interface WheelEventInput extends WheelGestureInput {
  /** Optional CSS x of the pointer at event time. */
  xCss?: number;
}

/** Pure: dispatch a wheel event into the controller, anchoring the
 *  zoom at the pointer location when supplied. */
export function dispatchWheel(controller: TimelineZoomController, event: WheelEventInput): void {
  const anchor: ZoomAnchor = event.xCss !== undefined ? xAnchor(event.xCss) : cursorAnchor();
  controller.applyWheelGesture(event, anchor);
}

/** Pure: dispatch a pinch event. */
export function dispatchPinch(
  controller: TimelineZoomController,
  ratio: number,
  anchor: ZoomAnchor = cursorAnchor(),
): void {
  controller.applyPinchGesture(ratio, anchor);
}

/** Convenience: build an anchor-resolve context for ad-hoc callers. */
export function makeAnchorContext(args: AnchorResolveContext): AnchorResolveContext {
  return args;
}
