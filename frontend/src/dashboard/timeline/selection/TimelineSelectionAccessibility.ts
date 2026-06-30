/**
 * Pure helpers that build screen-reader announcements for selection.
 */

import type { TimelineSelectionState } from "@/dashboard/timeline/selection/models/TimelineSelectionModels";

/** Pure: build a concise human-readable announcement for the
 *  current selection state. */
export function describeSelectionState(state: TimelineSelectionState): string {
  if (state.selectedTaskId === null) {
    return state.rowCount === 0 ? "No tasks tracked." : "No row selected.";
  }
  const label =
    state.selectedTask?.task_name ?? state.selectedTask?.coroutine_name ?? state.selectedTaskId;
  const position =
    state.selectedRowIndex >= 0
      ? `row ${state.selectedRowIndex + 1} of ${state.rowCount}`
      : `row out of range (${state.rowCount} total)`;
  return `Selected task ${label}, ${position}.`;
}

/** Pure: build an announcement for a navigation action. */
export function describeSelectionAction(
  action:
    | "select-next"
    | "select-previous"
    | "select-first"
    | "select-last"
    | "clear-selection"
    | "center-selection"
    | "reveal-selection",
): string {
  switch (action) {
    case "select-next":
      return "Moved selection down.";
    case "select-previous":
      return "Moved selection up.";
    case "select-first":
      return "Selected first task.";
    case "select-last":
      return "Selected last task.";
    case "clear-selection":
      return "Cleared selection.";
    case "center-selection":
      return "Centered viewport on selection.";
    case "reveal-selection":
      return "Revealed selection in viewport.";
  }
}
