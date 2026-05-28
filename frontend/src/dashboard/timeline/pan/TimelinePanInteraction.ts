/**
 * Pure mappers from canonical input events to controller calls.
 */

import type { TimelinePanController } from "@/dashboard/timeline/pan/TimelinePanController";

export interface PointerDragInput {
  pointerXCss: number;
  pointerTimeSeconds: number;
}

export interface PointerMoveInput {
  pointerXCss: number;
}

export interface WheelPanInput {
  deltaXPx: number;
}

export function dispatchDragStart(
  controller: TimelinePanController,
  event: PointerDragInput,
): void {
  controller.beginDrag(event);
}

export function dispatchDragMove(
  controller: TimelinePanController,
  event: PointerMoveInput,
): void {
  controller.updateDrag(event);
}

export function dispatchDragEnd(controller: TimelinePanController): void {
  controller.endDrag();
}

export function dispatchDragCancel(controller: TimelinePanController): void {
  controller.cancelDrag();
}

export function dispatchWheelPan(
  controller: TimelinePanController,
  event: WheelPanInput,
): void {
  controller.applyWheelGesture({ deltaXPx: event.deltaXPx });
}
