/**
 * Pixel dimensions of the timeline canvas.
 *
 * The viewport is HiDPI-aware: ``cssWidth`` / ``cssHeight`` describe
 * the layout box, ``devicePixelRatio`` scales the backing store.
 * Drawing code works in CSS pixels (the renderer ``ctx.scale(dpr,dpr)``
 * once per frame), so consumers never multiply by DPR themselves.
 */

export interface TimelineViewport {
  /** CSS-pixel width of the canvas. */
  cssWidth: number;
  /** CSS-pixel height of the canvas. */
  cssHeight: number;
  /** Backing-store device pixel ratio. */
  devicePixelRatio: number;
}

export const EMPTY_VIEWPORT: TimelineViewport = {
  cssWidth: 0,
  cssHeight: 0,
  devicePixelRatio: 1,
};

/** Build a viewport from a DOM element's size + DPR. */
export function viewportFromElement(width: number, height: number, dpr: number): TimelineViewport {
  return {
    cssWidth: Math.max(0, Math.floor(width)),
    cssHeight: Math.max(0, Math.floor(height)),
    devicePixelRatio: dpr > 0 && Number.isFinite(dpr) ? dpr : 1,
  };
}

/** Pure: ``true`` when two viewports are visibly identical. */
export function viewportEqual(a: TimelineViewport, b: TimelineViewport): boolean {
  return (
    a.cssWidth === b.cssWidth &&
    a.cssHeight === b.cssHeight &&
    a.devicePixelRatio === b.devicePixelRatio
  );
}

/** Pure: backing-store width in device pixels. */
export function viewportBackingWidth(v: TimelineViewport): number {
  return Math.round(v.cssWidth * v.devicePixelRatio);
}

/** Pure: backing-store height in device pixels. */
export function viewportBackingHeight(v: TimelineViewport): number {
  return Math.round(v.cssHeight * v.devicePixelRatio);
}
