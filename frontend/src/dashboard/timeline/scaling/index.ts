/**
 * Public surface of the canonical time-scaling engine.
 */

export {
  TimelineScaleEngine,
  type TimelineScaleEngineOptions,
} from "@/dashboard/timeline/scaling/TimelineScaleEngine";

export {
  TimelineTimeScale,
  safeScale,
} from "@/dashboard/timeline/scaling/TimelineTimeScale";

export {
  fitScaleToRange,
  panScale,
  screenXToTime,
  timeToScreenX,
  zoomScaleAroundTime,
  zoomScaleAroundX,
} from "@/dashboard/timeline/scaling/TimelineScaleTransforms";

export {
  clampDuration,
  isAtConstraintEdge,
  mergeConstraints,
} from "@/dashboard/timeline/scaling/TimelineScaleConstraints";

export {
  guardScaleBounds,
  isNearPrecisionFloor,
  type PrecisionGuardResult,
} from "@/dashboard/timeline/scaling/TimelineScalePrecision";

export {
  clampPhase,
  easeInOut as scaleEaseInOut,
  easeLinear,
  easeOutCubic,
  interpolateScaleFrame,
  sampleInterpolation,
} from "@/dashboard/timeline/scaling/TimelineScaleInterpolation";

export {
  generateTicks,
  type GenerateTicksOptions,
} from "@/dashboard/timeline/scaling/TimelineScaleTicks";

export {
  gridFromTicks,
  type TimelineScaleGridLines,
} from "@/dashboard/timeline/scaling/TimelineScaleGrid";

export {
  TimelineScaleTickCache,
} from "@/dashboard/timeline/scaling/TimelineScaleCache";

export {
  EMPTY_SCALE_VIEWPORT,
  viewportChanged,
  type ScaleViewport,
} from "@/dashboard/timeline/scaling/TimelineScaleViewport";

export {
  normalizeViewport,
  type NormalizeViewportArgs,
  type NormalizeViewportResult,
} from "@/dashboard/timeline/scaling/TimelineScaleNormalization";

export {
  ScaleInvalidationBus,
  type ScaleInvalidationKind,
  type ScaleInvalidationListener,
} from "@/dashboard/timeline/scaling/TimelineScaleInvalidation";

export {
  TimelineScaleMetrics,
  getTimelineScaleMetrics,
  resetTimelineScaleMetrics,
  type TimelineScaleMetricsSnapshot,
} from "@/dashboard/timeline/scaling/TimelineScaleMetrics";

export {
  getScaleDiagnosticsSnapshot,
  clearScaleTrace,
  getScaleTraceSnapshot,
  isScaleTraceEnabled,
  recordScaleTrace,
  setScaleTraceEnabled,
  type ScaleDiagnosticsSnapshot,
  type ScaleTraceEntry,
} from "@/dashboard/timeline/scaling/TimelineScaleDiagnostics";

export {
  traceConstraintHit,
  traceFit,
  traceNormalize,
  tracePan as traceScalePan,
  tracePrecisionWarning,
  traceScaleInvalidate,
  traceScaleSet,
  traceTickBuild,
  traceTickCacheHit,
  traceZoom,
} from "@/dashboard/timeline/scaling/TimelineScaleTracing";

export {
  DEFAULT_SCALE_CONSTRAINTS,
  type ScaleConstraints,
  type ScaleInterpolationFrame,
  type TimelineScaleSnapshot,
  type TimelineScaleTick,
  type TimelineTickList,
} from "@/dashboard/timeline/scaling/models/TimelineScaleModels";

export {
  SCALE_EPSILON_SECONDS,
  approximatelyEqual as scaleApproximatelyEqual,
  clamp as scaleClamp,
  durationTooSmall,
  isNumericallyUnsafe,
  snapToPixel as scaleSnapToPixel,
} from "@/dashboard/timeline/scaling/utils/numerics";

export { useTimelineDataRange } from "@/dashboard/timeline/scaling/selectors/storeScaleSelectors";
export { useTimelineScaleEngine } from "@/dashboard/timeline/scaling/hooks/useTimelineScaleEngine";
