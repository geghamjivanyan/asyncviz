/**
 * HiDPI canvas helpers.
 *
 * Centralised so the renderer never re-derives the backing-store math
 * itself. Calling :func:`resizeCanvasToViewport` is idempotent — it
 * only mutates the element when the new size differs from the current
 * one, which lets the renderer call it every frame without thrash.
 */

import type { TimelineViewport } from "@/dashboard/timeline/viewport/TimelineViewport";

/** Resize the canvas to match the viewport's CSS + backing dimensions.
 *  Returns ``true`` when an actual resize happened. */
export function resizeCanvasToViewport(
  canvas: HTMLCanvasElement,
  viewport: TimelineViewport,
): boolean {
  const cssWidth = viewport.cssWidth;
  const cssHeight = viewport.cssHeight;
  const backingWidth = Math.round(cssWidth * viewport.devicePixelRatio);
  const backingHeight = Math.round(cssHeight * viewport.devicePixelRatio);
  let changed = false;
  if (canvas.width !== backingWidth) {
    canvas.width = backingWidth;
    changed = true;
  }
  if (canvas.height !== backingHeight) {
    canvas.height = backingHeight;
    changed = true;
  }
  const styleWidth = `${cssWidth}px`;
  const styleHeight = `${cssHeight}px`;
  if (canvas.style.width !== styleWidth) {
    canvas.style.width = styleWidth;
    changed = true;
  }
  if (canvas.style.height !== styleHeight) {
    canvas.style.height = styleHeight;
    changed = true;
  }
  return changed;
}

/** Reset the canvas transform to CSS-pixel space + clear the frame. */
export function prepareFrame(ctx: CanvasRenderingContext2D, viewport: TimelineViewport): void {
  const dpr = viewport.devicePixelRatio;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, viewport.cssWidth, viewport.cssHeight);
}

/** Read the device pixel ratio defensively — falls back to 1 in
 *  environments where ``window`` is undefined (worker, tests). */
export function readDevicePixelRatio(): number {
  if (typeof window === "undefined") return 1;
  const dpr = window.devicePixelRatio;
  return dpr > 0 && Number.isFinite(dpr) ? dpr : 1;
}
