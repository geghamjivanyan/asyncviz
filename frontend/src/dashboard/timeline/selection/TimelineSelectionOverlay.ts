/**
 * Pure overlay snapshot builder.
 *
 * The renderer's :class:`SelectionLayer` already paints the selected
 * row's band; the overlay builder here surfaces the same data in a
 * normalized shape consumers (toolbar, a11y companion, future
 * tooltip) can read without subscribing to the renderer.
 */

import type {
  TimelineSelectionState,
} from "@/dashboard/timeline/selection/models/TimelineSelectionModels";

export interface SelectionOverlayPayload {
  /** Currently-selected task id. */
  selectedTaskId: string | null;
  /** Row index of the selection. */
  selectedRowIndex: number;
  /** Pre-computed top + bottom Y of the selection band in CSS pixels. */
  bandTopYCss: number | null;
  bandBottomYCss: number | null;
  /** Whether the selection sits inside the visible viewport rows. */
  insideViewport: boolean;
}

export interface BuildOverlayArgs {
  state: TimelineSelectionState;
  /** Camera's first visible row index (inclusive). */
  visibleStartRowIndex: number;
  /** Camera's last visible row index (exclusive). */
  visibleEndRowIndex: number;
  /** Camera row height in CSS pixels. */
  rowHeightPx: number;
  /** Camera's ``rowStart``. */
  rowStart: number;
}

/** Pure: build an overlay payload for the active selection. */
export function buildSelectionOverlay(args: BuildOverlayArgs): SelectionOverlayPayload {
  const { state, visibleStartRowIndex, visibleEndRowIndex, rowHeightPx, rowStart } = args;
  if (state.selectedRowIndex < 0 || state.selectedTaskId === null) {
    return {
      selectedTaskId: state.selectedTaskId,
      selectedRowIndex: state.selectedRowIndex,
      bandTopYCss: null,
      bandBottomYCss: null,
      insideViewport: false,
    };
  }
  const insideViewport =
    state.selectedRowIndex >= visibleStartRowIndex &&
    state.selectedRowIndex < visibleEndRowIndex;
  const bandTopYCss = (state.selectedRowIndex - rowStart) * rowHeightPx;
  const bandBottomYCss = bandTopYCss + rowHeightPx;
  return {
    selectedTaskId: state.selectedTaskId,
    selectedRowIndex: state.selectedRowIndex,
    bandTopYCss,
    bandBottomYCss,
    insideViewport,
  };
}
