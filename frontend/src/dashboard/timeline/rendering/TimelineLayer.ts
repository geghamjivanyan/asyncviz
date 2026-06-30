/**
 * Canonical layer contract.
 *
 * A layer is an isolated unit of drawing — grid, segments, selection,
 * overlay, diagnostics. Each layer:
 *
 *   * declares a stable :attr:`id`,
 *   * declares a :attr:`order` (lower is drawn first / behind),
 *   * receives a :type:`RenderContext` per frame and decides what to
 *     draw.
 *
 * Layers are framework-free TypeScript so they can run on a worker
 * thread later. They never read the store directly — data is passed
 * in via :attr:`RenderContext.scene`.
 */

import type { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import type { TimelineColorPalette } from "@/dashboard/timeline/rendering/TimelineColors";

export interface RenderScene {
  /** Number of rows in the active dataset. Used for culling. */
  totalRows: number;
  /** Visible rows already culled by the renderer. */
  rows: readonly TimelineRow[];
  /** Visible segments already culled by the renderer. */
  segments: readonly TimelineRenderSegment[];
  /** Currently selected row id, if any. */
  selectedTaskId: string | null;
  /** Cursor world-time when the user hovers; ``null`` otherwise. */
  cursorTimeSeconds: number | null;
}

export interface RenderContext {
  ctx: CanvasRenderingContext2D;
  coords: TimelineCoordinateSystem;
  palette: TimelineColorPalette;
  scene: RenderScene;
  /** Monotonic ms when the frame started — used by performance hooks. */
  frameStartMs: number;
}

/** Coarse lifecycle bucket the row renderer uses for styling. */
export type TimelineRowState =
  "created" | "running" | "waiting" | "completed" | "cancelled" | "failed" | "unknown";

/** Warning severity tier surfaced on a row. */
export type TimelineRowWarningSeverity = "info" | "warning" | "error" | "critical";

/** Replay marker — set when a row is highlighted by replay navigation. */
export interface TimelineRowReplayMark {
  /** Sequence id the replay session is currently parked on. */
  sequence: number | null;
  /** ``true`` when the row is the cursor's current focus. */
  focused: boolean;
}

export interface TimelineRow {
  /** Row index in the global ordering. */
  rowIndex: number;
  /** Task id linked to the row (stable React key). */
  taskId: string;
  /** Display label for the parallel a11y companion. */
  label: string;
  /** Coroutine name resolved from the task snapshot, when available. */
  coroutineName?: string | null;
  /** Lifecycle bucket — drives background styling + a11y semantics. */
  state?: TimelineRowState;
  /** Parent task id — feeds future lineage indentation + grouping. */
  parentTaskId?: string | null;
  /** Lineage depth (0 for roots). */
  depth?: number;
  /** Direct child count — surfaced in label badges. */
  childCount?: number;
  /** Highest warning severity touching this row, or ``null`` if clean. */
  warningSeverity?: TimelineRowWarningSeverity | null;
  /** Number of active warnings related to the row. */
  warningCount?: number;
  /** Replay highlight metadata. */
  replay?: TimelineRowReplayMark | null;
  /** Stable monotonic create time (ns) used for deterministic ordering. */
  createdAtMonotonicNs?: number;
}

/** Coarse lifecycle bucket the segment renderer maps to styling. */
export type TimelineSegmentLifecycleState =
  | "running"
  | "waiting"
  | "sleeping"
  | "blocked"
  | "completed"
  | "cancelled"
  | "failed"
  | "replaying"
  | "orphaned"
  | "unknown";

/** Replay highlight metadata attached to a segment. */
export interface TimelineSegmentReplayMark {
  /** Sequence id the cursor is currently parked on. */
  sequence: number | null;
  /** ``true`` when this is the segment under the replay cursor. */
  focused: boolean;
  /** ``true`` when this segment was finalized before the replay sequence. */
  finalizedBeforeCursor?: boolean;
}

export interface TimelineRenderSegment {
  segmentId: string;
  rowIndex: number;
  taskId: string;
  startSeconds: number;
  endSeconds: number;
  /** Coarse intent used by :func:`segmentFill`. */
  intent: "default" | "run" | "wait" | "completed" | "cancelled" | "failed";
  /** ``true`` for active (still-running) segments. */
  isActive: boolean;
  /** Fine-grained lifecycle state — drives styling decisions. Optional
   *  for backwards compatibility; the segment renderer falls back to
   *  ``intent`` when absent. */
  lifecycleState?: TimelineSegmentLifecycleState;
  /** Sequence range that produced this segment (start..end inclusive). */
  sequenceStart?: number | null;
  sequenceEnd?: number | null;
  /** Pre-computed duration in nanoseconds; populated when known. */
  durationNs?: number;
  /** Highest warning severity touching the segment (or the parent task). */
  warningSeverity?: TimelineRowWarningSeverity | null;
  /** Replay highlight metadata. */
  replay?: TimelineSegmentReplayMark | null;
  /** Lineage parent id — surfaces in tooltips + grouping. */
  parentTaskId?: string | null;
  /** Lineage depth, mirrored from the row projection when present. */
  depth?: number;
}

export interface TimelineLayer {
  /** Stable identifier — used by diagnostics + tests. */
  readonly id: string;
  /** Lower values draw first (behind). */
  readonly order: number;
  /** Whether the layer is currently active. Toggled by diagnostics. */
  enabled: boolean;
  /** Draw the layer's contents. */
  render(context: RenderContext): void;
}
