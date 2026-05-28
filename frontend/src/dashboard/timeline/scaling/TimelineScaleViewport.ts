/**
 * Lightweight viewport bookkeeping shared by the scaling engine.
 *
 * The renderer's :type:`TimelineViewport` carries CSS + backing
 * dimensions; the scale engine only needs the CSS width + DPR. The
 * holder centralises that subset so future viewport changes (e.g.
 * vertical scaling) don't ripple into every caller.
 */

export interface ScaleViewport {
  widthPx: number;
  devicePixelRatio: number;
}

export const EMPTY_SCALE_VIEWPORT: ScaleViewport = Object.freeze({
  widthPx: 0,
  devicePixelRatio: 1,
});

/** Pure: ``true`` when two viewports differ in any field. */
export function viewportChanged(a: ScaleViewport, b: ScaleViewport): boolean {
  return a.widthPx !== b.widthPx || a.devicePixelRatio !== b.devicePixelRatio;
}
