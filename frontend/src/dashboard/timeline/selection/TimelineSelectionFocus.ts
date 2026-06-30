/**
 * Pure helpers for the selection's *viewport focus* — the math
 * the controller runs when it wants to reveal the selection inside
 * the visible viewport.
 *
 * The helpers are framework + controller agnostic so they can drive
 * future focus controllers (debugger jump-to-task, replay focus
 * mode) without depending on the React glue.
 */

export interface FocusBounds {
  /** Inclusive start of the selection's time range. */
  startSeconds: number;
  /** Exclusive end of the selection's time range. */
  endSeconds: number;
}

export interface VisibleWindow {
  startSeconds: number;
  endSeconds: number;
}

/** Pure: ``true`` when the selection range sits fully inside the
 *  visible window. */
export function selectionFullyVisible(selection: FocusBounds, visible: VisibleWindow): boolean {
  return (
    selection.startSeconds >= visible.startSeconds && selection.endSeconds <= visible.endSeconds
  );
}

/** Pure: ``true`` when the selection range overlaps the visible
 *  window at all. */
export function selectionAtLeastPartiallyVisible(
  selection: FocusBounds,
  visible: VisibleWindow,
): boolean {
  return (
    selection.endSeconds >= visible.startSeconds && selection.startSeconds <= visible.endSeconds
  );
}

/** Pure: compute the new ``timeStart`` that would center the
 *  selection inside a visible window of ``durationSeconds``. */
export function centerWindowOnSelection(selection: FocusBounds, durationSeconds: number): number {
  const mid = (selection.startSeconds + selection.endSeconds) / 2;
  return mid - durationSeconds / 2;
}

/** Pure: compute the *minimum* pan delta required to bring the
 *  selection fully inside the visible window. Returns ``0`` when the
 *  selection is already enclosed. */
export function minimalRevealDelta(
  selection: FocusBounds,
  visible: VisibleWindow,
  options: { paddingSeconds?: number } = {},
): number {
  const padding = Math.max(0, options.paddingSeconds ?? 0);
  const leftEdge = visible.startSeconds + padding;
  const rightEdge = visible.endSeconds - padding;
  if (selection.startSeconds < leftEdge) {
    return selection.startSeconds - leftEdge;
  }
  if (selection.endSeconds > rightEdge) {
    return selection.endSeconds - rightEdge;
  }
  return 0;
}
