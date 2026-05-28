/**
 * Public surface of the live task table system.
 *
 * Consumers should import from this barrel — the internal layout
 * (components/hooks/selectors/utils/models) is allowed to change
 * without breaking callers.
 */

export { TaskTable } from "@/dashboard/tasks/components/TaskTable";
export type { TaskTableProps } from "@/dashboard/tasks/components/TaskTable";
export { TaskTableContainer } from "@/dashboard/tasks/components/TaskTableContainer";
export type { TaskTableContainerProps } from "@/dashboard/tasks/components/TaskTableContainer";
export { TaskTableHeader } from "@/dashboard/tasks/components/TaskTableHeader";
export { TaskTableBody } from "@/dashboard/tasks/components/TaskTableBody";
export { TaskRow } from "@/dashboard/tasks/components/TaskRow";
export type { TaskRowProps } from "@/dashboard/tasks/components/TaskRow";
export { TaskCell } from "@/dashboard/tasks/components/TaskCell";
export { TaskStatusBadge } from "@/dashboard/tasks/components/TaskStatusBadge";
export { TaskDurationCell } from "@/dashboard/tasks/components/TaskDurationCell";
export { TaskTimelineCell } from "@/dashboard/tasks/components/TaskTimelineCell";
export { TaskWarningCell } from "@/dashboard/tasks/components/TaskWarningCell";
export { TaskMetricsCell } from "@/dashboard/tasks/components/TaskMetricsCell";
export { TaskToolbar } from "@/dashboard/tasks/components/TaskToolbar";
export { TaskDiagnostics } from "@/dashboard/tasks/components/TaskDiagnostics";

export {
  type TaskRow as TaskRowData,
  type TaskRowStatus,
  type TaskRowWarningSummary,
  type TaskRowTimelineSummary,
  type TaskRowMetricsSummary,
  buildTaskRow,
  deriveTaskRowStatus,
  summarizeRowWarnings,
  deriveRowLabel,
  shortenTaskId,
  compareRowsForStableOrder,
  rowSignature,
  WARNING_SEVERITY_WEIGHT,
} from "@/dashboard/tasks/models/taskRow";

export {
  COLUMN_LOOKUP,
  DEFAULT_VISIBLE_COLUMNS,
  TASK_COLUMNS,
  type TaskColumnDefinition,
  type TaskColumnId,
  compareRowsByColumn,
} from "@/dashboard/tasks/models/columns";

export {
  DEFAULT_FILTERS,
  DEFAULT_SORT,
  isDefaultFilterState,
  type SortDirection,
  type TaskFilterState,
  type TaskSortState,
} from "@/dashboard/tasks/models/filters";

export {
  applyFilterAndSort,
  comparatorForColumn,
  filterRows,
  sortRows,
} from "@/dashboard/tasks/utils/sortFilter";

export {
  buildParentExistsSet,
  groupWarningsByTask,
  warningsForTask,
} from "@/dashboard/tasks/utils/grouping";

export {
  formatDuration,
  formatStartTime,
  formatTaskIdShort,
  formatWarningCount,
} from "@/dashboard/tasks/utils/format";

export { projectTaskRows, type ProjectionInputs } from "@/dashboard/tasks/selectors/projectRows";

export {
  useProjectedTaskRow,
  useProjectedTaskRows,
} from "@/dashboard/tasks/selectors/storeSelectors";

export { useTaskRows } from "@/dashboard/tasks/hooks/useTaskRows";
export { useTaskTableState } from "@/dashboard/tasks/hooks/useTaskTableState";
export type { TaskTableStateValue } from "@/dashboard/tasks/hooks/useTaskTableState";
export { useTaskSelection } from "@/dashboard/tasks/hooks/useTaskSelection";
export type { TaskSelectionValue } from "@/dashboard/tasks/hooks/useTaskSelection";
export {
  TASK_ROW_HEIGHT_PX,
  useVirtualization,
  type VirtualizationWindow,
} from "@/dashboard/tasks/hooks/useVirtualization";

export {
  TaskTableMetrics,
  type TaskTableMetricsSnapshot,
  getTaskTableMetrics,
  resetTaskTableMetrics,
} from "@/dashboard/tasks/observability";
