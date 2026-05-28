/**
 * Tiny holder for the viewport state the zoom controller needs.
 *
 * The controller doesn't subscribe to the canvas's viewport directly
 * — consumers push the cursor position + viewport width through this
 * helper so the controller doesn't grow a DOM dependency.
 */

export interface ZoomViewportContext {
  /** Most recent cursor world-time the consumer observed. */
  cursorTimeSeconds: number | null;
  /** Most recent CSS pointer x relative to the canvas. */
  cursorXCss: number | null;
}

export const EMPTY_ZOOM_VIEWPORT_CONTEXT: ZoomViewportContext = Object.freeze({
  cursorTimeSeconds: null,
  cursorXCss: null,
});

export function withCursor(
  _context: ZoomViewportContext,
  cursorTimeSeconds: number | null,
  cursorXCss: number | null,
): ZoomViewportContext {
  return { cursorTimeSeconds, cursorXCss };
}
