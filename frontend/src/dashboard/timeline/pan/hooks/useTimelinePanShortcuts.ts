/**
 * Hook that binds the canonical pan shortcuts to the window.
 */

import { useEffect } from "react";
import type { TimelinePanController } from "@/dashboard/timeline/pan/TimelinePanController";
import {
  DEFAULT_PAN_SHORTCUTS,
  matchPanShortcut,
  type PanShortcutBinding,
} from "@/dashboard/timeline/pan/TimelinePanShortcuts";

export interface UseTimelinePanShortcutsArgs {
  controller: TimelinePanController | null;
  bindings?: readonly PanShortcutBinding[];
  /** Range used for ``Home`` / ``End`` shortcuts. */
  dataRange?: { startSeconds: number; endSeconds: number } | null;
  disabled?: boolean;
}

export function useTimelinePanShortcuts(args: UseTimelinePanShortcutsArgs): void {
  const { controller, bindings, dataRange, disabled } = args;
  useEffect(() => {
    if (controller === null || disabled) return;
    const list = bindings ?? DEFAULT_PAN_SHORTCUTS;
    const handler = (event: KeyboardEvent): void => {
      const action = matchPanShortcut(event, list);
      if (action === null) return;
      event.preventDefault();
      switch (action) {
        case "pan-left":
          controller.panLeft();
          break;
        case "pan-right":
          controller.panRight();
          break;
        case "pan-left-fast":
          controller.panLeft({ shift: true });
          break;
        case "pan-right-fast":
          controller.panRight({ shift: true });
          break;
        case "pan-home":
          if (dataRange) controller.panToTime(dataRange.startSeconds);
          break;
        case "pan-end":
          if (dataRange) {
            const state = controller.currentState();
            controller.panToTime(dataRange.endSeconds - state.durationSeconds);
          }
          break;
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [controller, bindings, dataRange, disabled]);
}
