/**
 * Tiny viewport-context holder used by the pan controller.
 *
 * The controller doesn't bind to the DOM directly — consumers push
 * the latest cursor position + viewport width through this helper so
 * the controller stays framework-free.
 */

export interface PanViewportContext {
  /** Current pointer x in CSS pixels (relative to the canvas). */
  pointerXCss: number | null;
  /** Current viewport width in CSS pixels. */
  widthPx: number;
}

export const EMPTY_PAN_VIEWPORT: PanViewportContext = Object.freeze({
  pointerXCss: null,
  widthPx: 0,
});

export function withPointer(
  context: PanViewportContext,
  pointerXCss: number | null,
): PanViewportContext {
  return { ...context, pointerXCss };
}
