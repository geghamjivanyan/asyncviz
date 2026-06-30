/**
 * Pure dispatch helpers that route hit-test results into the
 * canonical selection controller.
 */

import type { TimelineSelectionController } from "@/dashboard/timeline/selection/TimelineSelectionController";

export interface HitResult {
  /** Selected task id, or ``null`` for empty space. */
  taskId: string | null;
}

/** Pure: dispatch a pointer hit into the controller. */
export function dispatchPointerHit(controller: TimelineSelectionController, hit: HitResult): void {
  if (hit.taskId === null) {
    controller.clearSelection("pointer");
  } else {
    controller.selectRow(hit.taskId, "pointer");
  }
}

/** Pure: deselect when the user clicks empty space (e.g. canvas
 *  background). */
export function dispatchEmptyClick(controller: TimelineSelectionController): void {
  controller.clearSelection("pointer");
}
