/**
 * Types for the canonical timeline zoom controller.
 *
 * The controller exposes zoom semantics in two flavors:
 *
 *   * factor-space — multiplicative deltas applied to the current
 *     scale window (``factor = 0.5`` zooms in 2×, ``factor = 2`` zooms
 *     out 2×),
 *   * level-space — normalized ``[0, 1]`` between the scale's
 *     ``maxDuration`` (level 0 = zoomed out) and ``minDuration`` (level
 *     1 = zoomed in to the limit).
 *
 * Level-space is what the toolbar + keyboard shortcuts speak; factor
 * space is what gestures speak. The controller is the single chokepoint
 * that converts between them.
 */

/** Where the zoom should pivot. */
export type ZoomAnchorKind = "time" | "x" | "center" | "cursor";

export interface ZoomAnchor {
  kind: ZoomAnchorKind;
  /** World time when ``kind === "time"``. */
  timeSeconds?: number;
  /** CSS x when ``kind === "x"``. */
  xCss?: number;
}

/** Snapshot of the zoom controller's observable state. */
export interface TimelineZoomState {
  /** Visible duration in seconds. */
  durationSeconds: number;
  /** Normalized level in ``[0, 1]`` — 0 = max duration, 1 = min duration. */
  level: number;
  /** ``true`` when no further zoom-in is possible. */
  atMin: boolean;
  /** ``true`` when no further zoom-out is possible. */
  atMax: boolean;
  /** Minimum allowed duration (seconds) per the active constraints. */
  minDurationSeconds: number;
  /** Maximum allowed duration (seconds) per the active constraints. */
  maxDurationSeconds: number;
  /** Pre-computed pixels per second at the current scale. */
  pixelsPerSecond: number;
  /** Engine-side scale identity — consumers can compare by ``===``. */
  scaleKey: string;
}

/** Stable preset focus targets. */
export type ZoomPresetKind =
  "fit-all" | "fit-selection" | "fit-active" | "fit-replay" | "fit-default";

export interface ZoomPreset {
  kind: ZoomPresetKind;
  startSeconds: number;
  endSeconds: number;
  /** Optional label surfaced in the toolbar / a11y companion. */
  label?: string;
}

/** Configurable thresholds the controller defaults to. */
export interface ZoomConfig {
  /** Multiplicative step applied by ``zoomIn()`` / ``zoomOut()``. */
  stepFactor: number;
  /** Pixels-per-line scaler used to translate wheel deltas. */
  wheelLinePx: number;
  /** Damping applied to wheel-mode deltas. */
  wheelFactorScale: number;
  /** Damping applied to pixel-mode deltas. */
  wheelPixelScale: number;
}

export const DEFAULT_ZOOM_CONFIG: ZoomConfig = Object.freeze({
  stepFactor: 0.66,
  wheelLinePx: 16,
  wheelFactorScale: 0.0015,
  wheelPixelScale: 0.0005,
});
