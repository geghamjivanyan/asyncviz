/**
 * Public façade over the pure row-navigation helpers.
 *
 * Keeps :class:`TimelineSelectionController` callers honest — they
 * only depend on the high-level navigation surface, not the
 * underlying utils.
 */

export {
  firstTaskId,
  indexOfTask,
  isAtFirst,
  isAtLast,
  lastTaskId,
  nextTaskId,
  previousTaskId,
  rowAt,
} from "@/dashboard/timeline/selection/utils/rowNavigation";
export type { SelectableRow } from "@/dashboard/timeline/selection/models/TimelineSelectionModels";
