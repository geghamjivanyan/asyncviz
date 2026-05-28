/**
 * Public surface of the canvas timeline renderer.
 */

export { TimelineCanvas } from "@/dashboard/timeline/components/TimelineCanvas";
export type {
  TimelineCanvasPointerEvent,
  TimelineCanvasProps,
} from "@/dashboard/timeline/components/TimelineCanvas";
export { TimelineContainer } from "@/dashboard/timeline/components/TimelineContainer";
export type { TimelineContainerProps } from "@/dashboard/timeline/components/TimelineContainer";
export { TimelineAccessibleSummary } from "@/dashboard/timeline/components/TimelineAccessibleSummary";
export type { TimelineAccessibleSummaryProps } from "@/dashboard/timeline/components/TimelineAccessibleSummary";
export { TimelineDiagnostics } from "@/dashboard/timeline/components/TimelineDiagnostics";

export {
  TimelineRenderer,
  EMPTY_DATASET,
  type TimelineDataset,
  type TimelineRendererOptions,
} from "@/dashboard/timeline/rendering/TimelineRenderer";
export { TimelineSceneGraph } from "@/dashboard/timeline/rendering/TimelineSceneGraph";
export { GridLayer, type GridLayerOptions } from "@/dashboard/timeline/rendering/GridLayer";
export {
  SegmentLayer,
  type SegmentLayerOptions,
} from "@/dashboard/timeline/rendering/SegmentLayer";
export {
  SelectionLayer,
  type SelectionLayerOptions,
} from "@/dashboard/timeline/rendering/SelectionLayer";
export {
  OverlayLayer,
  type OverlayLayerOptions,
} from "@/dashboard/timeline/rendering/OverlayLayer";
export type {
  RenderContext,
  RenderScene,
  TimelineLayer,
  TimelineRenderSegment,
  TimelineRow,
} from "@/dashboard/timeline/rendering/TimelineLayer";
export {
  DEFAULT_TIMELINE_PALETTE,
  segmentFill,
  type TimelineColorPalette,
} from "@/dashboard/timeline/rendering/TimelineColors";

export {
  TimelineCoordinateSystem,
  makeCoordinateSystem,
  type VisibleRowRange,
  type VisibleSegmentSpan,
} from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
export {
  DEFAULT_CAMERA,
  DEFAULT_ROW_HEIGHT_PX,
  cameraDuration,
  cameraEqual,
  clampRowStart,
  fitCameraToRange,
  panCamera,
  scrollCamera,
  setRowHeight,
  zoomCameraAroundTime,
  type TimelineCamera,
} from "@/dashboard/timeline/viewport/TimelineCamera";
export {
  EMPTY_VIEWPORT,
  viewportEqual,
  viewportBackingHeight,
  viewportBackingWidth,
  viewportFromElement,
  type TimelineViewport,
} from "@/dashboard/timeline/viewport/TimelineViewport";
export {
  cullRows,
  cullSegments,
  type CullableRow,
  type CullableSegment,
} from "@/dashboard/timeline/viewport/TimelineCulling";

export {
  TimelineScheduler,
  type DirtyReason,
  type SchedulerMetricsSnapshot,
  type SchedulerOptions,
} from "@/dashboard/timeline/scheduler/TimelineScheduler";

export { hitTest, type HitTestResult } from "@/dashboard/timeline/interaction/TimelineHitTesting";

export {
  projectTimeline,
  EMPTY_PROJECTION,
  type TimelineProjection,
  type TimelineProjectionInputs,
} from "@/dashboard/timeline/selectors/projectTimeline";
export { useTimelineProjection } from "@/dashboard/timeline/selectors/storeSelectors";

export {
  useTimelineCamera,
  type TimelineCameraStateValue,
  type UseTimelineCameraOptions,
} from "@/dashboard/timeline/hooks/useTimelineCamera";
export { useElementViewport } from "@/dashboard/timeline/hooks/useResizeObserver";
export {
  useTimelineRenderer,
  type TimelineRendererControl,
  type UseTimelineRendererOptions,
} from "@/dashboard/timeline/hooks/useTimelineRenderer";

export { formatTickLabel, pickTickInterval } from "@/dashboard/timeline/utils/ticks";
export {
  prepareFrame,
  readDevicePixelRatio,
  resizeCanvasToViewport,
} from "@/dashboard/timeline/utils/canvas";

export {
  TimelineRendererMetrics,
  type TimelineRendererMetricsSnapshot,
  getTimelineRendererMetrics,
  resetTimelineRendererMetrics,
} from "@/dashboard/timeline/observability";

export {
  clearRendererTrace,
  getRendererTraceSnapshot,
  isRendererTraceEnabled,
  recordRendererTrace,
  setRendererTraceEnabled,
  type RendererTraceEntry,
} from "@/dashboard/timeline/diagnostics/trace";

export * from "@/dashboard/timeline/rows";
export * from "@/dashboard/timeline/segments";
export * from "@/dashboard/timeline/live";
export * from "@/dashboard/timeline/virtualization";
export * from "@/dashboard/timeline/scaling";
export * from "@/dashboard/timeline/zoom";
export * from "@/dashboard/timeline/pan";
export * from "@/dashboard/timeline/selection";

export {
  TimelineRenderScheduler,
  type RenderOptimizationConfig,
  type RenderOptimizationDiagnostics,
  type RenderOptimizationMetricsSnapshot,
  RenderPriority,
  default_config as defaultRenderOptimizationConfig,
  lean_config as leanRenderOptimizationConfig,
  relaxed_config as relaxedRenderOptimizationConfig,
} from "@/dashboard/timeline/rendering_optimization";
