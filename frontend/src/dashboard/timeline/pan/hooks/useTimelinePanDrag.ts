/**
 * React adapter that wires pointer events on a canvas element into
 * the canonical pan controller.
 *
 * The hook listens for ``pointerdown`` on the element, then captures
 * ``pointermove`` / ``pointerup`` / ``pointercancel`` events to drive
 * the drag lifecycle. The optional ``timeAt`` callback translates
 * the pointer's CSS x into world time at the moment the drag begins.
 *
 * The hook is intentionally narrow — it doesn't know about zoom,
 * about row selection, or about the renderer. Consumers compose it
 * alongside the existing pointer handlers.
 */

import { type RefObject, useEffect } from "react";
import type { TimelinePanController } from "@/dashboard/timeline/pan/TimelinePanController";

export interface UseTimelinePanDragArgs {
  /** Element that captures the pointer events. */
  targetRef: RefObject<HTMLElement | null>;
  controller: TimelinePanController | null;
  /** Convert a pointer x to world time at drag-start. */
  timeAt: (pointerXCss: number) => number;
  /** When ``false``, the listener is removed (useful for read-only
   *  modes). */
  enabled?: boolean;
  /** Pointer button that initiates the drag — defaults to 0 (left). */
  button?: number;
}

export function useTimelinePanDrag(args: UseTimelinePanDragArgs): void {
  const { targetRef, controller, timeAt, enabled = true, button = 0 } = args;

  useEffect(() => {
    if (!enabled || controller === null) return;
    const target = targetRef.current;
    if (target === null) return;

    let pointerId: number | null = null;

    const handlePointerDown = (event: PointerEvent): void => {
      if (event.button !== button) return;
      pointerId = event.pointerId;
      const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
      const xCss = event.clientX - rect.left;
      controller.beginDrag({ pointerXCss: xCss, pointerTimeSeconds: timeAt(xCss) });
      try {
        target.setPointerCapture(event.pointerId);
      } catch {
        // setPointerCapture can throw on misbehaving polyfills — best-effort.
      }
    };

    const handlePointerMove = (event: PointerEvent): void => {
      if (pointerId !== event.pointerId) return;
      const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
      const xCss = event.clientX - rect.left;
      controller.updateDrag({ pointerXCss: xCss });
    };

    const handlePointerEnd = (event: PointerEvent): void => {
      if (pointerId !== event.pointerId) return;
      pointerId = null;
      controller.endDrag();
      try {
        target.releasePointerCapture(event.pointerId);
      } catch {
        // ignored
      }
    };

    const handlePointerCancel = (event: PointerEvent): void => {
      if (pointerId !== event.pointerId) return;
      pointerId = null;
      controller.cancelDrag();
    };

    target.addEventListener("pointerdown", handlePointerDown);
    target.addEventListener("pointermove", handlePointerMove);
    target.addEventListener("pointerup", handlePointerEnd);
    target.addEventListener("pointercancel", handlePointerCancel);
    return () => {
      target.removeEventListener("pointerdown", handlePointerDown);
      target.removeEventListener("pointermove", handlePointerMove);
      target.removeEventListener("pointerup", handlePointerEnd);
      target.removeEventListener("pointercancel", handlePointerCancel);
    };
  }, [targetRef, controller, timeAt, enabled, button]);
}
