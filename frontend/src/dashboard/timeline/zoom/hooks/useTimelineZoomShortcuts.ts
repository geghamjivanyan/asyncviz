/**
 * React adapter that binds the canonical zoom shortcuts to the
 * window.
 *
 * The hook listens for ``keydown`` on the window, matches the
 * incoming event against :data:`DEFAULT_ZOOM_SHORTCUTS`, and routes
 * the matched action to the controller. Bindings are intentionally
 * keyed off the platform modifier so macOS users see ``Cmd`` while
 * Linux / Windows users see ``Ctrl``.
 */

import { useEffect } from "react";
import type { TimelineZoomController } from "@/dashboard/timeline/zoom/TimelineZoomController";
import {
  DEFAULT_ZOOM_SHORTCUTS,
  matchShortcut,
  type ZoomShortcutBinding,
} from "@/dashboard/timeline/zoom/TimelineZoomShortcuts";

export interface UseTimelineZoomShortcutsArgs {
  controller: TimelineZoomController | null;
  /** Optional override of the binding list. */
  bindings?: readonly ZoomShortcutBinding[];
  /** Optional fit-all range; required for the ``fit-all`` shortcut. */
  fitRange?: { startSeconds: number; endSeconds: number } | null;
  /** Optional reset range for the ``zoom-reset`` shortcut. Falls back
   *  to ``fitRange`` when omitted. */
  resetRange?: { startSeconds: number; endSeconds: number } | null;
  /** Disable the listener (useful when the timeline is hidden). */
  disabled?: boolean;
}

export function useTimelineZoomShortcuts(args: UseTimelineZoomShortcutsArgs): void {
  const { controller, bindings, fitRange, resetRange, disabled } = args;
  useEffect(() => {
    if (controller === null || disabled) return;
    const list = bindings ?? DEFAULT_ZOOM_SHORTCUTS;
    const handler = (event: KeyboardEvent): void => {
      const action = matchShortcut(event, list);
      if (action === null) return;
      // Suppress browser zoom default for the action we own.
      event.preventDefault();
      controller.recordShortcut(action);
      switch (action) {
        case "zoom-in":
          controller.zoomIn();
          break;
        case "zoom-out":
          controller.zoomOut();
          break;
        case "zoom-reset": {
          const range = resetRange ?? fitRange ?? null;
          if (range) controller.zoomToRange(range.startSeconds, range.endSeconds, "fit-default");
          break;
        }
        case "fit-all":
          if (fitRange)
            controller.zoomToRange(fitRange.startSeconds, fitRange.endSeconds, "fit-all");
          break;
      }
    };
    window.addEventListener("keydown", handler);
    return () => {
      window.removeEventListener("keydown", handler);
    };
  }, [controller, bindings, fitRange, resetRange, disabled]);
}
