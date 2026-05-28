/**
 * Tiny viewport-context holder for the selection controller.
 *
 * The controller doesn't read the canvas viewport directly —
 * consumers push the latest viewport snapshot (camera state +
 * dimensions) so the controller can run focus / centering logic
 * without a DOM dependency.
 */

export interface SelectionViewportContext {
  /** Visible time-window start in world seconds. */
  visibleStartSeconds: number;
  /** Visible time-window end in world seconds. */
  visibleEndSeconds: number;
  /** First visible row index. */
  visibleStartRowIndex: number;
  /** Exclusive upper bound for visible rows. */
  visibleEndRowIndex: number;
  /** Pre-computed visible duration. */
  durationSeconds: number;
}

export const EMPTY_SELECTION_VIEWPORT: SelectionViewportContext = Object.freeze({
  visibleStartSeconds: 0,
  visibleEndSeconds: 1,
  visibleStartRowIndex: 0,
  visibleEndRowIndex: 0,
  durationSeconds: 1,
});

export function withVisibleTime(
  context: SelectionViewportContext,
  startSeconds: number,
  endSeconds: number,
): SelectionViewportContext {
  return {
    ...context,
    visibleStartSeconds: startSeconds,
    visibleEndSeconds: endSeconds,
    durationSeconds: Math.max(0, endSeconds - startSeconds),
  };
}

export function withVisibleRows(
  context: SelectionViewportContext,
  startRowIndex: number,
  endRowIndex: number,
): SelectionViewportContext {
  return {
    ...context,
    visibleStartRowIndex: Math.max(0, Math.floor(startRowIndex)),
    visibleEndRowIndex: Math.max(0, Math.floor(endRowIndex)),
  };
}
