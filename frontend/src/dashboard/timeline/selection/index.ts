/**
 * Public surface of the canonical task-row selection controller.
 */

export {
  TimelineSelectionController,
  type SelectionFocusAdapter,
  type SelectionRowSource,
  type SelectionStateListener,
  type SelectionViewportSource,
  type TimelineSelectionControllerOptions,
} from "@/dashboard/timeline/selection/TimelineSelectionController";

export {
  buildSelectionState,
  type BuildSelectionStateArgs,
} from "@/dashboard/timeline/selection/TimelineSelectionState";

export {
  makeRuntimeSelectionStore,
  type SelectionStore,
} from "@/dashboard/timeline/selection/TimelineSelectionStore";

export {
  firstTaskId as firstSelectableTaskId,
  indexOfTask as selectionIndexOfTask,
  isAtFirst as selectionIsAtFirst,
  isAtLast as selectionIsAtLast,
  lastTaskId as lastSelectableTaskId,
  nextTaskId as nextSelectableTaskId,
  previousTaskId as previousSelectableTaskId,
  rowAt as selectableRowAt,
} from "@/dashboard/timeline/selection/TimelineSelectionNavigation";

export {
  decodeSelection,
  encodeSelection,
  selectionPayloadsEqual,
  type SelectionPersistencePayload,
} from "@/dashboard/timeline/selection/TimelineSelectionPersistence";

export {
  buildHighlight,
  EMPTY_HIGHLIGHT,
  type BuildHighlightArgs,
  type HighlightIntent,
  type HighlightSnapshot,
} from "@/dashboard/timeline/selection/TimelineSelectionHighlight";

export {
  buildSelectionOverlay,
  type BuildOverlayArgs,
  type SelectionOverlayPayload,
} from "@/dashboard/timeline/selection/TimelineSelectionOverlay";

export {
  centerWindowOnSelection,
  minimalRevealDelta,
  selectionAtLeastPartiallyVisible,
  selectionFullyVisible,
  type FocusBounds,
  type VisibleWindow,
} from "@/dashboard/timeline/selection/TimelineSelectionFocus";

export {
  anchorFromHit,
  anchorFromSegment,
  anchorFromTime,
  anchorsEqual,
} from "@/dashboard/timeline/selection/TimelineSelectionAnchoring";

export {
  EMPTY_SELECTION_VIEWPORT,
  withVisibleRows,
  withVisibleTime,
  type SelectionViewportContext,
} from "@/dashboard/timeline/selection/TimelineSelectionViewport";

export {
  TimelineSelectionMetrics,
  getTimelineSelectionMetrics,
  resetTimelineSelectionMetrics,
  type TimelineSelectionMetricsSnapshot,
} from "@/dashboard/timeline/selection/TimelineSelectionMetrics";

export {
  getSelectionDiagnosticsSnapshot,
  clearSelectionTrace,
  getSelectionTraceSnapshot,
  isSelectionTraceEnabled,
  recordSelectionTrace,
  setSelectionTraceEnabled,
  type SelectionDiagnosticsSnapshot,
  type SelectionTraceEntry,
} from "@/dashboard/timeline/selection/TimelineSelectionDiagnostics";

export {
  traceSelectionCenter,
  traceSelectionClear,
  traceSelectionNavigate,
  traceSelectionNoop,
  traceSelectionRestore,
  traceSelectionReveal,
  traceSelectionSelect,
} from "@/dashboard/timeline/selection/TimelineSelectionTracing";

export {
  dispatchEmptyClick,
  dispatchPointerHit,
  type HitResult,
} from "@/dashboard/timeline/selection/TimelineSelectionInteraction";

export {
  DEFAULT_SELECTION_SHORTCUTS,
  hasPlatformModifier as selectionHasPlatformModifier,
  matchSelectionShortcut,
  type KeyboardEventLike as SelectionKeyboardEventLike,
  type SelectionShortcutAction,
  type SelectionShortcutBinding,
} from "@/dashboard/timeline/selection/TimelineSelectionShortcuts";

export {
  describeSelectionAction,
  describeSelectionState,
} from "@/dashboard/timeline/selection/TimelineSelectionAccessibility";

export {
  DEFAULT_SELECTION_CONFIG,
  EMPTY_SELECTION_ANCHOR,
  type SelectableRow,
  type SelectionAnchor,
  type SelectionConfig,
  type SelectionReason,
  type TimelineSelectionState,
} from "@/dashboard/timeline/selection/models/TimelineSelectionModels";

export {
  TimelineSelectionToolbar,
  type TimelineSelectionToolbarProps,
} from "@/dashboard/timeline/selection/TimelineSelectionToolbar";

export {
  useSelectableRows,
  useTaskLookup,
  useTaskRangeLookup,
} from "@/dashboard/timeline/selection/selectors/storeSelectionSelectors";
export { useTimelineSelectionController } from "@/dashboard/timeline/selection/hooks/useTimelineSelectionController";
export { useTimelineSelectionShortcuts } from "@/dashboard/timeline/selection/hooks/useTimelineSelectionShortcuts";
