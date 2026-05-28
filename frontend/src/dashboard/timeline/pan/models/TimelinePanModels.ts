/**
 * Types for the canonical timeline pan controller.
 *
 * The controller owns three orthogonal panning surfaces:
 *
 *   * **drag** — pointer drag converted to a continuous pan in
 *     world-time space (the cursor stays glued to the timeline
 *     coordinate it grabbed),
 *   * **wheel** — horizontal wheel / trackpad deltas converted to
 *     time deltas,
 *   * **step** — keyboard arrow keys converted to a fraction-of-
 *     viewport pan.
 *
 * Every pan operation eventually calls
 * :meth:`TimelinePanController.panBySeconds`; everything else is
 * sugar.
 */

/** Snapshot of the controller's observable state. */
export interface TimelinePanState {
  /** Active scale window, mirrored from the scale engine. */
  timeStartSeconds: number;
  timeEndSeconds: number;
  /** Pre-computed visible duration. */
  durationSeconds: number;
  /** Pre-computed pixels per second. */
  pixelsPerSecond: number;
  /** ``true`` when a drag is in flight. */
  dragging: boolean;
  /** ``true`` when no further pan-left is possible. */
  atMinTime: boolean;
  /** ``true`` when no further pan-right is possible. */
  atMaxTime: boolean;
  /** Optional pan bounds (when the controller is bounded). */
  minTimeSeconds: number | null;
  maxTimeSeconds: number | null;
  /** Stable identity for cache lookups — compare by ``===``. */
  scaleKey: string;
}

/** Pan limits — optional bounds the controller clamps against. */
export interface PanBounds {
  /** Lowest world second the viewport's left edge may reach. */
  minTimeSeconds: number | null;
  /** Highest world second the viewport's right edge may reach. */
  maxTimeSeconds: number | null;
}

export const UNBOUNDED_PAN: PanBounds = Object.freeze({
  minTimeSeconds: null,
  maxTimeSeconds: null,
});

/** Tuning knobs the controller defaults to. */
export interface PanConfig {
  /** Fraction of the visible window panned per arrow-key step. */
  keyboardStepFraction: number;
  /** Multiplier applied to ``Shift + arrow`` panning. */
  shiftMultiplier: number;
  /** Horizontal wheel damping (seconds per pixel). */
  wheelSecondsPerPixel: number;
  /** Threshold below which a velocity sample is treated as a hover. */
  velocityNoiseSecondsPerMs: number;
}

export const DEFAULT_PAN_CONFIG: PanConfig = Object.freeze({
  keyboardStepFraction: 0.15,
  shiftMultiplier: 4,
  wheelSecondsPerPixel: 0,
  velocityNoiseSecondsPerMs: 0,
});

/** Drag anchor — captured at the moment the pointer goes down. */
export interface PanDragAnchor {
  /** Pointer x in CSS pixels at drag-start. */
  pointerXCss: number;
  /** Pointer's world time at drag-start. */
  pointerTimeSeconds: number;
  /** Scale window's left edge at drag-start. */
  initialTimeStartSeconds: number;
  /** Scale window's right edge at drag-start. */
  initialTimeEndSeconds: number;
  /** Monotonic ms when the drag started. */
  startedAtMs: number;
}

/** Single velocity sample collected during a drag. */
export interface PanVelocitySample {
  /** Seconds the viewport moved since the previous sample. */
  deltaSeconds: number;
  /** Wall ms since the previous sample. */
  deltaMs: number;
  /** Monotonic ms when the sample was captured. */
  atMs: number;
}

/** Coarse classification of an in-flight pan. */
export type PanReason =
  | "drag"
  | "wheel"
  | "keyboard"
  | "center"
  | "to-time"
  | "manual"
  | "inertial";
