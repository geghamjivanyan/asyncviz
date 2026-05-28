/**
 * Types for the canonical task-row selection controller.
 *
 * The controller owns three orthogonal surfaces:
 *
 *   * **pointer** — pointer clicks on the canvas resolve into row +
 *     segment selection,
 *   * **keyboard** — Arrow / Home / End / Enter steps navigate the
 *     deterministic row order,
 *   * **programmatic** — toolbar buttons + future replay controllers
 *     call ``selectRow`` / ``clearSelection`` directly.
 *
 * Selection is single-row today; multi-select lives behind an
 * intentionally forward-compatible interface so the future shift-
 * click / band-select hooks land without churning callers.
 */

import type { TaskSnapshot } from "@/types/runtime";

/** Coarse classification of an in-flight selection mutation. */
export type SelectionReason =
  | "pointer"
  | "keyboard"
  | "programmatic"
  | "restore"
  | "store"
  | "clear";

/** Snapshot of the controller's observable state. */
export interface TimelineSelectionState {
  /** Currently-selected task id, or ``null``. */
  selectedTaskId: string | null;
  /** Row index of the selected task, or ``-1`` when nothing selected. */
  selectedRowIndex: number;
  /** Snapshot of the selected task — convenience for consumers. */
  selectedTask: TaskSnapshot | null;
  /** Total rows in the active projection. */
  rowCount: number;
  /** ``true`` when the selection is the first row (boundary checks). */
  atFirst: boolean;
  /** ``true`` when the selection is the last row. */
  atLast: boolean;
  /** Reason for the most recent change. */
  lastReason: SelectionReason | null;
  /** Stable identity for cache lookups — flips on every change. */
  generation: number;
}

/** Minimal row contract the selection controller depends on. */
export interface SelectableRow {
  rowIndex: number;
  taskId: string;
}

/** Optional anchor associated with a selection — used by tooltip /
 *  overlay paths. */
export interface SelectionAnchor {
  /** World time the user clicked, when the selection came from a
   *  pointer. ``null`` for keyboard / programmatic selection. */
  timeSeconds: number | null;
  /** Segment id under the pointer, when available. */
  segmentId: string | null;
}

export const EMPTY_SELECTION_ANCHOR: SelectionAnchor = Object.freeze({
  timeSeconds: null,
  segmentId: null,
});

/** Config knobs the controller defaults to. */
export interface SelectionConfig {
  /** Auto-center the viewport on selection changes via the supplied
   *  pan controller. */
  autoCenter: boolean;
  /** When auto-centering, only fire when the selection is fully
   *  offscreen. */
  centerOnlyWhenOffscreen: boolean;
  /** Auto-zoom-to-fit on selection — disabled by default. */
  autoZoomToFit: boolean;
}

export const DEFAULT_SELECTION_CONFIG: SelectionConfig = Object.freeze({
  autoCenter: false,
  centerOnlyWhenOffscreen: true,
  autoZoomToFit: false,
});
