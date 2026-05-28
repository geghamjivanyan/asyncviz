/**
 * View models for runtime freeze-region rendering.
 *
 * A :type:`FreezeRegion` is the canonical timeline-side projection of
 * one blocking-warning group. It carries everything the renderer +
 * inspectors need without re-reading the underlying wire shape:
 *
 *   * the freeze identity (group id + warning id + window id),
 *   * the world-time span (seconds) the freeze covers,
 *   * the severity + lifecycle bucket the renderer styles against,
 *   * the metadata an accessibility companion announces.
 *
 * Projection is pure; live updates fold into the blocking-warning
 * store first and then re-project through :func:`projectFreezeRegions`.
 */

import type {
  BlockingGroupSeverity,
  BlockingGroupState,
} from "@/dashboard/warnings/blocking/models/BlockingWarningModels";

/** Coarse intent the renderer uses for fill / stroke decisions. */
export type FreezeRegionIntent = "warning" | "critical" | "freeze" | "resolved";

/**
 * Lifecycle bucket that drives styling. ``"active"`` covers both
 * opened/escalating/active emitter states — they all paint the same
 * way (with a slight pulse opacity bump on active). ``"recovered"``
 * covers both recovered + expired; the renderer dims them uniformly.
 */
export type FreezeRegionLifecycle = "active" | "recovered";

export interface FreezeRegionView {
  /** Stable identity — sourced from the blocking-warning group id. */
  groupId: string;
  /** Warning id — used by the inspector + accessibility label. */
  warningId: string;
  /** Window id (nullable for the "no-window" bucket). */
  windowId: string | null;
  /** Runtime id — surfaces in future distributed monitoring overlays. */
  runtimeId: string;
  /** World-time start in seconds (monotonic, mirrors timeline scale). */
  startSeconds: number;
  /** World-time end in seconds. */
  endSeconds: number;
  /** Pre-computed duration in seconds (end - start, ≥ 0). */
  durationSeconds: number;
  /** Severity tier driving styling. */
  severity: BlockingGroupSeverity;
  /** Peak severity seen — used for escalation badging. */
  peakSeverity: BlockingGroupSeverity;
  /** Lifecycle bucket used by the renderer. */
  lifecycle: FreezeRegionLifecycle;
  /** Original emitter state — passed through for accessibility labels. */
  state: BlockingGroupState;
  /** Intent token consumed by the styling palette. */
  intent: FreezeRegionIntent;
  /** Peak lag observed during the freeze, in nanoseconds. */
  peakLagNs: number;
  /** Number of correlated stack captures. */
  captureCount: number;
  /** Number of escalation transitions recorded. */
  escalationCount: number;
  /** Correlated task id (when the emitter pinned the freeze to a task). */
  taskId: string | null;
  /** Correlated task name. */
  taskName: string | null;
  /** Stable monotonic-ns instant the freeze first opened. Used as a
   *  secondary sort key + replay seek. */
  firstSeenNs: number;
  /** Monotonic-ns instant the freeze was last seen / closed. */
  lastSeenNs: number;
}

/** Render-time geometry attached to a region by :class:`FreezeRegionRenderer`. */
export interface FreezeRegionGeometry {
  /** Region identity. */
  groupId: string;
  /** Left edge in CSS pixels. */
  xStart: number;
  /** Right edge in CSS pixels. */
  xEnd: number;
  /** Pixel width (always > 0). */
  width: number;
  /** ``true`` when the freeze is fully inside the visible window. */
  fullyVisible: boolean;
  /** ``true`` when the freeze starts before the visible window (clipped left). */
  clippedLeft: boolean;
  /** ``true`` when the freeze ends after the visible window (clipped right). */
  clippedRight: boolean;
}

/** Optional bookmark a host can stash on the store for replay anchoring. */
export interface FreezeRegionBookmark {
  groupId: string;
  monotonicNs: number;
}
