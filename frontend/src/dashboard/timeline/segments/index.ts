/**
 * Public surface of the timeline-segment rendering system.
 */

export {
  TimelineSegmentRenderer,
  type TimelineSegmentRendererOptions,
} from "@/dashboard/timeline/segments/TimelineSegmentRenderer";

export {
  TimelineSegmentLayout,
  makeSegmentLayout,
  type TimelineSegmentLayoutOptions,
  type TimelineSegmentLayoutSnapshot,
} from "@/dashboard/timeline/segments/TimelineSegmentLayout";

export {
  projectTimelineSegments,
  type TimelineSegmentProjectionInputs,
} from "@/dashboard/timeline/segments/TimelineSegmentProjection";

export {
  EMPTY_TIMELINE_SEGMENT_PROJECTION,
  type TimelineSegmentProjection,
  type TimelineSegmentProjectionEntry,
} from "@/dashboard/timeline/segments/models/TimelineSegmentModels";

export {
  projectSegmentRect,
  crispStrokeRect,
  type SegmentScreenRect,
} from "@/dashboard/timeline/segments/TimelineSegmentGeometry";

export {
  resolveSegmentStyle,
  cancelStrikeColor,
  failedBorderColor,
  type SegmentStyle,
  type SegmentStyleArgs,
  type SegmentTextureKind,
} from "@/dashboard/timeline/segments/TimelineSegmentStyling";

export {
  segmentActiveStroke,
  segmentCancelStrike,
  segmentFailedBorder,
  segmentHatchStroke,
  segmentLifecycleFill,
  segmentReplayFill,
  segmentReplayStroke,
  segmentSelectionFill,
  segmentSelectionStroke,
  segmentWarningStroke,
} from "@/dashboard/timeline/segments/TimelineSegmentColors";

export { TimelineSegmentTextureCache } from "@/dashboard/timeline/segments/TimelineSegmentTextures";

export {
  animationPhase,
  easeInOut,
  oscillator,
  prefersReducedMotion,
  type ClockFn,
} from "@/dashboard/timeline/segments/TimelineSegmentAnimations";

export {
  renderSegmentWarning,
  type SegmentWarningRenderArgs,
} from "@/dashboard/timeline/segments/TimelineSegmentWarnings";

export {
  renderSegmentSelection,
  type SegmentSelectionArgs,
} from "@/dashboard/timeline/segments/TimelineSegmentSelection";

export {
  cancelledStrikeDecorator,
  defaultSegmentDecorators,
  failedBorderDecorator,
  SegmentDecoratorRegistry,
  type SegmentDecorator,
  type SegmentDecoratorContext,
} from "@/dashboard/timeline/segments/TimelineSegmentDecorators";

export {
  TimelineSegmentGeometryCache,
  cameraKey,
  layoutKey,
} from "@/dashboard/timeline/segments/TimelineSegmentCaching";

export {
  resolveVisibleSegments,
  segmentsOverlap,
  type SegmentVisibilityOptions,
  type SegmentVisibilityResult,
} from "@/dashboard/timeline/segments/TimelineSegmentVirtualization";

export {
  hitTestSegment,
  type SegmentHitTestArgs,
  type SegmentHitTestResult,
} from "@/dashboard/timeline/segments/TimelineSegmentHitTesting";

export {
  flatGrouping as flatSegmentGrouping,
  groupByLineageParent as groupSegmentsByLineageParent,
  groupByTask as groupSegmentsByTask,
  type TimelineSegmentGroup,
  type TimelineSegmentGrouping,
} from "@/dashboard/timeline/segments/TimelineSegmentGrouping";

export {
  TimelineSegmentMetrics,
  getTimelineSegmentMetrics,
  resetTimelineSegmentMetrics,
  type TimelineSegmentMetricsSnapshot,
} from "@/dashboard/timeline/segments/TimelineSegmentMetrics";

export {
  getSegmentDiagnosticsSnapshot,
  clearSegmentTrace,
  getSegmentTraceSnapshot,
  isSegmentTraceEnabled,
  recordSegmentTrace,
  setSegmentTraceEnabled,
  type SegmentDiagnosticsSnapshot,
  type SegmentTraceEntry,
} from "@/dashboard/timeline/segments/TimelineSegmentDiagnostics";

export { normalizeSegment } from "@/dashboard/timeline/segments/utils/normalizeSegment";

export { useTimelineSegmentProjection } from "@/dashboard/timeline/segments/selectors/storeSegmentSelectors";
export { useTimelineSegmentRenderer } from "@/dashboard/timeline/segments/hooks/useTimelineSegmentRenderer";
