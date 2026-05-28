/**
 * Hook that binds the canonical selection shortcuts to the window.
 */

import { useEffect } from "react";
import type { TimelineSelectionController } from "@/dashboard/timeline/selection/TimelineSelectionController";
import {
  DEFAULT_SELECTION_SHORTCUTS,
  matchSelectionShortcut,
  type SelectionShortcutBinding,
} from "@/dashboard/timeline/selection/TimelineSelectionShortcuts";

export interface UseTimelineSelectionShortcutsArgs {
  controller: TimelineSelectionController | null;
  bindings?: readonly SelectionShortcutBinding[];
  disabled?: boolean;
}

export function useTimelineSelectionShortcuts(
  args: UseTimelineSelectionShortcutsArgs,
): void {
  const { controller, bindings, disabled } = args;
  useEffect(() => {
    if (controller === null || disabled) return;
    const list = bindings ?? DEFAULT_SELECTION_SHORTCUTS;
    const handler = (event: KeyboardEvent): void => {
      const action = matchSelectionShortcut(event, list);
      if (action === null) return;
      // Don't hijack form input — selection shortcuts only fire
      // outside editable surfaces.
      const target = event.target as HTMLElement | null;
      if (
        target !== null &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }
      event.preventDefault();
      switch (action) {
        case "select-next":
          controller.selectNext();
          break;
        case "select-previous":
          controller.selectPrevious();
          break;
        case "select-first":
          controller.selectFirst();
          break;
        case "select-last":
          controller.selectLast();
          break;
        case "clear-selection":
          controller.clearSelection("keyboard");
          break;
        case "center-selection":
          controller.centerOnSelection();
          break;
        case "reveal-selection":
          controller.revealSelection();
          break;
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [controller, bindings, disabled]);
}
