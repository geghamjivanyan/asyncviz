/**
 * Pure helper that builds a :type:`TimelineSelectionState` from a
 * row source + a selected-task id.
 *
 * The controller already does this internally; the helper exists so
 * external consumers (toolbar previews, debugger overlays) can build
 * the same shape without owning a controller.
 */

import type { TaskSnapshot } from "@/types/runtime";
import {
  indexOfTask,
  isAtFirst,
  isAtLast,
} from "@/dashboard/timeline/selection/utils/rowNavigation";
import type {
  SelectableRow,
  SelectionReason,
  TimelineSelectionState,
} from "@/dashboard/timeline/selection/models/TimelineSelectionModels";

export interface BuildSelectionStateArgs {
  rows: readonly SelectableRow[];
  selectedTaskId: string | null;
  selectedTask?: TaskSnapshot | null;
  reason?: SelectionReason;
  generation?: number;
}

export function buildSelectionState(args: BuildSelectionStateArgs): TimelineSelectionState {
  const selectedRowIndex = indexOfTask(args.rows, args.selectedTaskId);
  return {
    selectedTaskId: args.selectedTaskId,
    selectedRowIndex,
    selectedTask: args.selectedTask ?? null,
    rowCount: args.rows.length,
    atFirst: isAtFirst(args.rows, args.selectedTaskId),
    atLast: isAtLast(args.rows, args.selectedTaskId),
    lastReason: args.reason ?? null,
    generation: args.generation ?? 0,
  };
}
