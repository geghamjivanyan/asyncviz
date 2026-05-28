/**
 * Public surface of the canonical timeline pan controller.
 */

export {
  TimelinePanController,
  type TimelinePanControllerOptions,
  type PanStateListener,
} from "@/dashboard/timeline/pan/TimelinePanController";

export {
  buildPanState,
} from "@/dashboard/timeline/pan/TimelinePanState";

export {
  isPastClickThreshold,
  makeDragAnchor,
  timeStartFromAnchor,
} from "@/dashboard/timeline/pan/TimelinePanAnchoring";

export {
  dragDeltaToSeconds,
  stepsToPanSeconds,
  wheelToPanSeconds,
} from "@/dashboard/timeline/pan/TimelinePanGestures";

export {
  clampPanTimeStart,
  mergeBounds,
  panWouldExceedBound,
  viewportEdgeState,
  type BoundedPanInputs,
} from "@/dashboard/timeline/pan/TimelinePanConstraints";

export {
  TimelinePanMomentum,
  decayVelocity,
  type MomentumOptions,
} from "@/dashboard/timeline/pan/TimelinePanMomentum";

export {
  interpolatePanTimeStart,
  panEaseInOut,
  panEaseLinear,
  panEaseOutCubic,
} from "@/dashboard/timeline/pan/TimelinePanInterpolation";

export {
  EMPTY_PAN_VIEWPORT,
  withPointer,
  type PanViewportContext,
} from "@/dashboard/timeline/pan/TimelinePanViewport";

export {
  TimelinePanMetrics,
  getTimelinePanMetrics,
  resetTimelinePanMetrics,
  type TimelinePanMetricsSnapshot,
} from "@/dashboard/timeline/pan/TimelinePanMetrics";

export {
  getPanDiagnosticsSnapshot,
  clearPanTrace,
  getPanTraceSnapshot,
  isPanTraceEnabled,
  recordPanTrace,
  setPanTraceEnabled,
  type PanDiagnosticsSnapshot,
  type PanTraceEntry,
} from "@/dashboard/timeline/pan/TimelinePanDiagnostics";

export {
  tracePan,
  tracePanCenter,
  tracePanConstraintHit,
  tracePanDragCancel,
  tracePanDragEnd,
  tracePanDragStart,
  tracePanDragUpdate,
  tracePanKeyboard,
  tracePanNoop,
  tracePanToTime,
  tracePanWheel,
} from "@/dashboard/timeline/pan/TimelinePanTracing";

export {
  dispatchDragCancel,
  dispatchDragEnd,
  dispatchDragMove,
  dispatchDragStart,
  dispatchWheelPan,
  type PointerDragInput,
  type PointerMoveInput,
  type WheelPanInput,
} from "@/dashboard/timeline/pan/TimelinePanInteraction";

export {
  DEFAULT_PAN_SHORTCUTS,
  hasPlatformModifier as panHasPlatformModifier,
  matchPanShortcut,
  type PanShortcutAction,
  type PanShortcutBinding,
  type KeyboardEventLike as PanKeyboardEventLike,
} from "@/dashboard/timeline/pan/TimelinePanShortcuts";

export {
  describePanAction,
  describePanState,
} from "@/dashboard/timeline/pan/TimelinePanAccessibility";

export {
  atBoundEdge as panAtBoundEdge,
  clampTimeStart as panClampTimeStart,
  deltaToCenter as panDeltaToCenter,
  deltaToTimeStart as panDeltaToTimeStart,
  wouldExceedBound as panWouldExceedBoundRaw,
} from "@/dashboard/timeline/pan/utils/panMath";

export {
  DEFAULT_PAN_CONFIG,
  UNBOUNDED_PAN,
  type PanBounds,
  type PanConfig,
  type PanDragAnchor,
  type PanReason,
  type PanVelocitySample,
  type TimelinePanState,
} from "@/dashboard/timeline/pan/models/TimelinePanModels";

export {
  TimelinePanToolbar,
  type TimelinePanToolbarProps,
} from "@/dashboard/timeline/pan/TimelinePanToolbar";

export { useTimelinePanController } from "@/dashboard/timeline/pan/hooks/useTimelinePanController";
export { useTimelinePanDrag } from "@/dashboard/timeline/pan/hooks/useTimelinePanDrag";
export { useTimelinePanShortcuts } from "@/dashboard/timeline/pan/hooks/useTimelinePanShortcuts";
