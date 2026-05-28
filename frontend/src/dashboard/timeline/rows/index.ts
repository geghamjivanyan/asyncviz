/**
 * Public surface of the timeline-row rendering system.
 *
 * Anything that lives under :mod:`@/dashboard/timeline/rows` and is
 * worth consuming from outside the package should be re-exported here.
 */

export {
  TimelineRowRenderer,
  type TimelineRowRendererOptions,
} from "@/dashboard/timeline/rows/TimelineRowRenderer";

export {
  TimelineRowLayout,
  makeRowLayout,
  type TimelineRowLayoutOptions,
  type TimelineRowLayoutSnapshot,
} from "@/dashboard/timeline/rows/TimelineRowLayout";

export {
  projectTimelineRows,
  type TimelineRowProjectionInputs,
} from "@/dashboard/timeline/rows/TimelineRowProjection";

export {
  EMPTY_TIMELINE_ROW_PROJECTION,
  type TimelineRowProjection,
  type TimelineRowProjectionEntry,
} from "@/dashboard/timeline/rows/models/TimelineRowModels";

export {
  rowBackgroundFill,
  rowReplayFill,
  rowReplayStroke,
  rowSecondaryText,
  rowSelectionFill,
  rowSelectionStroke,
  rowSeparatorStroke,
  rowStateIndicator,
  rowWarningStroke,
  rowWarningTint,
  withAlpha,
} from "@/dashboard/timeline/rows/TimelineRowColors";

export {
  TimelineRowLabelRenderer,
  truncateText,
  type RowLabelRendererOptions,
  type RowLabelRenderArgs,
} from "@/dashboard/timeline/rows/TimelineRowLabels";

export {
  renderRowSelection,
  type RowSelectionRenderArgs,
} from "@/dashboard/timeline/rows/TimelineRowSelection";

export {
  renderRowWarnings,
  type RowWarningRenderArgs,
} from "@/dashboard/timeline/rows/TimelineRowWarnings";

export {
  defaultRowDecorators,
  lineageCaretDecorator,
  RowDecoratorRegistry,
  stateIndicatorDecorator,
  type RowDecorator,
  type RowDecoratorContext,
} from "@/dashboard/timeline/rows/TimelineRowDecorators";

export {
  resolveVisibleRows,
  virtualContentHeight,
  type RowVisibilityOptions,
  type RowVisibilityResult,
} from "@/dashboard/timeline/rows/TimelineRowVirtualization";

export {
  TimelineRowTextCache,
  type CachedLabel,
} from "@/dashboard/timeline/rows/TimelineRowCaching";

export { TimelineRowTextureCache } from "@/dashboard/timeline/rows/TimelineRowTextures";

export {
  flatGrouping,
  groupByLineageRoot,
  type TimelineRowGroup,
  type TimelineRowGrouping,
} from "@/dashboard/timeline/rows/TimelineRowGrouping";

export {
  hitTestRow,
  rowBoundingBox,
  type RowHitTestArgs,
  type RowHitTestResult,
  type TimelineRowZone,
} from "@/dashboard/timeline/rows/TimelineRowHitTesting";

export {
  resolveHover,
  resolvePrimaryClick,
  type RowInteractionEvent,
  type RowInteractionKind,
} from "@/dashboard/timeline/rows/TimelineRowInteraction";

export {
  TimelineRowMetrics,
  getTimelineRowMetrics,
  resetTimelineRowMetrics,
  type TimelineRowMetricsSnapshot,
} from "@/dashboard/timeline/rows/TimelineRowMetrics";

export {
  getRowDiagnosticsSnapshot,
  clearRowTrace,
  getRowTraceSnapshot,
  isRowTraceEnabled,
  recordRowTrace,
  setRowTraceEnabled,
  type RowDiagnosticsSnapshot,
  type RowRendererTraceEntry,
} from "@/dashboard/timeline/rows/TimelineRowDiagnostics";

export { normalizeRow } from "@/dashboard/timeline/rows/utils/normalizeRow";

export { useTimelineRowProjection } from "@/dashboard/timeline/rows/selectors/storeRowSelectors";
export { useTimelineRowRenderer } from "@/dashboard/timeline/rows/hooks/useTimelineRowRenderer";
