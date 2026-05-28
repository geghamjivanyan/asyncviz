/**
 * Public surface for the canonical freeze-region visualization
 * module. Importers should reach for this barrel instead of the deep
 * file paths so the module boundary stays stable.
 */

export {
  FreezeRegionRenderer,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionRenderer";
export type {
  FreezeRegionSource,
  FreezeRegionRendererOptions,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionRenderer";

export * from "@/dashboard/timeline/freeze_regions/models/FreezeRegionModels";

export {
  projectFreezeRegion,
  projectFreezeRegions,
} from "@/dashboard/timeline/freeze_regions/selectors/projectFreezeRegions";

export {
  compareFreezeKeys,
  intentForFreeze,
  isTerminalState,
  lifecycleForState,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionSeverity";

export {
  DEFAULT_FREEZE_REGION_PALETTE,
  freezeBodyFill,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionColors";
export type {
  FreezeRegionPalette,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionColors";

export {
  MIN_FREEZE_PIXEL_WIDTH,
  computeFreezeGeometry,
  cullVisibleFreezeRegions,
  pointInGeometry,
  snapMarkerX,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionGeometry";

export {
  drawFreezeEdgeMarkers,
  drawEscalationMarkers,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionMarkers";

export {
  resolveBodyStyle,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionStyling";

export {
  PULSE_PERIOD_MS,
  PULSE_AMPLITUDE,
  makePulseFn,
  pulseMultiplier,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionAnimations";

export {
  DEFAULT_VISIBLE_FREEZE_CAP,
  clampFreezeRegions,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionVirtualization";

export {
  hitTestFreezeRegions,
  nearestFreezeRegion,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionHitTesting";
export type {
  FreezeHitTestEntry,
  FreezeHitTestResult,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionHitTesting";

export {
  describeFreezeForAccessibility,
  describeFreezeCountsAnnouncement,
  describeFreezeFocusAnnouncement,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionAccessibility";

export {
  useFreezeRegionStore,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionStore";
export type {
  FreezeRegionStoreState,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionStore";

export {
  useFreezeRegionProjection,
} from "@/dashboard/timeline/freeze_regions/hooks/useFreezeRegionProjection";
export type {
  FreezeRegionProjection,
} from "@/dashboard/timeline/freeze_regions/hooks/useFreezeRegionProjection";

export {
  useFreezeRegionLayer,
} from "@/dashboard/timeline/freeze_regions/hooks/useFreezeRegionLayer";
export type {
  UseFreezeRegionLayerOptions,
} from "@/dashboard/timeline/freeze_regions/hooks/useFreezeRegionLayer";

export {
  useFreezeRegionInteractions,
} from "@/dashboard/timeline/freeze_regions/hooks/useFreezeRegionInteractions";
export type {
  FreezeInteractionHandlers,
  UseFreezeRegionInteractionsOptions,
} from "@/dashboard/timeline/freeze_regions/hooks/useFreezeRegionInteractions";

export {
  getFreezeRegionMetrics,
  resetFreezeRegionMetrics,
} from "@/dashboard/timeline/freeze_regions/diagnostics/FreezeRegionMetricsCollector";
export type {
  FreezeRegionMetricsSnapshot,
} from "@/dashboard/timeline/freeze_regions/diagnostics/FreezeRegionMetricsCollector";

export {
  clearFreezeRegionTrace,
  getFreezeRegionTraceSnapshot,
  isFreezeRegionTraceEnabled,
  recordFreezeRegionTrace,
  setFreezeRegionTraceEnabled,
} from "@/dashboard/timeline/freeze_regions/diagnostics/FreezeRegionTracing";
export type {
  FreezeRegionTraceEntry,
  FreezeRegionTraceKind,
} from "@/dashboard/timeline/freeze_regions/diagnostics/FreezeRegionTracing";

export { FreezeRegionDiagnostics } from "@/dashboard/timeline/freeze_regions/FreezeRegionDiagnostics";
