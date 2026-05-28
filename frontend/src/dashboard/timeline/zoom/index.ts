/**
 * Public surface of the canonical timeline zoom controller.
 */

export {
  TimelineZoomController,
  type TimelineZoomControllerOptions,
  type ZoomStateListener,
} from "@/dashboard/timeline/zoom/TimelineZoomController";

export {
  buildZoomState,
} from "@/dashboard/timeline/zoom/TimelineZoomState";

export {
  centerAnchor,
  cursorAnchor,
  resolveAnchorTime,
  timeAnchor,
  xAnchor,
  type AnchorResolveContext,
} from "@/dashboard/timeline/zoom/TimelineZoomAnchoring";

export {
  pinchToZoomFactor,
  stepsToZoomFactor,
  wheelToZoomFactor,
  type WheelDeltaMode,
  type WheelGestureInput,
} from "@/dashboard/timeline/zoom/TimelineZoomGestures";

export {
  checkDurationAgainstConstraints,
  wouldBreachConstraints,
  type ConstraintCheck,
} from "@/dashboard/timeline/zoom/TimelineZoomConstraints";

export {
  interpolateZoomRange,
  zoomEaseInOut,
  zoomEaseLinear,
  zoomEaseOutCubic,
  zoomInterpolate,
  zoomSamplePhases,
  type ZoomInterpolationFrame,
} from "@/dashboard/timeline/zoom/TimelineZoomInterpolation";

export {
  isUsableRange,
  mergeRanges,
  padRange,
  type FocusRange,
} from "@/dashboard/timeline/zoom/TimelineZoomFocus";

export {
  findPreset,
  makePreset,
  resolvePresets,
  type PresetSourceContext,
} from "@/dashboard/timeline/zoom/TimelineZoomPresets";

export {
  describeZoomAction,
  describeZoomState,
} from "@/dashboard/timeline/zoom/TimelineZoomAccessibility";

export {
  EMPTY_ZOOM_VIEWPORT_CONTEXT,
  withCursor,
  type ZoomViewportContext,
} from "@/dashboard/timeline/zoom/TimelineZoomViewport";

export {
  TimelineZoomMetrics,
  getTimelineZoomMetrics,
  resetTimelineZoomMetrics,
  type TimelineZoomMetricsSnapshot,
} from "@/dashboard/timeline/zoom/TimelineZoomMetrics";

export {
  getZoomDiagnosticsSnapshot,
  clearZoomTrace,
  getZoomTraceSnapshot,
  isZoomTraceEnabled,
  recordZoomTrace,
  setZoomTraceEnabled,
  type ZoomDiagnosticsSnapshot,
  type ZoomTraceEntry,
} from "@/dashboard/timeline/zoom/TimelineZoomDiagnostics";

export {
  traceZoomByFactor,
  traceZoomFit,
  traceZoomIn,
  traceZoomNoop,
  traceZoomOut,
  traceZoomPinch,
  traceZoomPreset,
  traceZoomSetLevel,
  traceZoomShortcut,
  traceZoomWheel,
} from "@/dashboard/timeline/zoom/TimelineZoomTracing";

export {
  dispatchPinch,
  dispatchWheel,
  makeAnchorContext,
  type WheelEventInput,
} from "@/dashboard/timeline/zoom/TimelineZoomInteraction";

export {
  DEFAULT_ZOOM_SHORTCUTS,
  hasPlatformModifier,
  matchShortcut,
  type KeyboardEventLike,
  type ZoomShortcutAction,
  type ZoomShortcutBinding,
} from "@/dashboard/timeline/zoom/TimelineZoomShortcuts";

export {
  durationToLevel,
  factorFromLevelDelta,
  levelToDuration,
  type LevelBounds,
} from "@/dashboard/timeline/zoom/utils/levelMath";

export {
  DEFAULT_ZOOM_CONFIG,
  type TimelineZoomState,
  type ZoomAnchor,
  type ZoomAnchorKind,
  type ZoomConfig,
  type ZoomPreset,
  type ZoomPresetKind,
} from "@/dashboard/timeline/zoom/models/TimelineZoomModels";

export {
  TimelineZoomToolbar,
  type TimelineZoomToolbarProps,
} from "@/dashboard/timeline/zoom/TimelineZoomToolbar";

export {
  TimelineZoomControls,
  type TimelineZoomControlsProps,
} from "@/dashboard/timeline/zoom/TimelineZoomControls";

export { useSelectedTaskSegmentRange } from "@/dashboard/timeline/zoom/selectors/storeZoomSelectors";
export { useTimelineZoomController } from "@/dashboard/timeline/zoom/hooks/useTimelineZoomController";
export { useTimelineZoomShortcuts } from "@/dashboard/timeline/zoom/hooks/useTimelineZoomShortcuts";
