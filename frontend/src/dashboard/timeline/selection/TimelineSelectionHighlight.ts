/**
 * Highlight model — describes the *visual* layers the selection
 * paints on top of the canonical row / segment layers.
 *
 * The renderer is the source of truth for paint instructions today;
 * this module ships a small helper that builds a snapshot the
 * accessibility companion + toolbar can render.
 */

export type HighlightIntent = "selection" | "replay" | "warning" | "focus";

export interface HighlightSnapshot {
  /** Currently selected task id, or ``null``. */
  taskId: string | null;
  /** Highlight intent — chooses the visual treatment. */
  intent: HighlightIntent;
  /** ``true`` when the highlight should pulse / animate. */
  pulse: boolean;
}

export const EMPTY_HIGHLIGHT: HighlightSnapshot = Object.freeze({
  taskId: null,
  intent: "selection",
  pulse: false,
});

export interface BuildHighlightArgs {
  selectedTaskId: string | null;
  hasWarning?: boolean;
  inReplay?: boolean;
}

/** Pure: build a highlight snapshot for the active selection. */
export function buildHighlight(args: BuildHighlightArgs): HighlightSnapshot {
  if (args.selectedTaskId === null) return EMPTY_HIGHLIGHT;
  let intent: HighlightIntent = "selection";
  if (args.inReplay) intent = "replay";
  else if (args.hasWarning) intent = "warning";
  return {
    taskId: args.selectedTaskId,
    intent,
    pulse: Boolean(args.inReplay),
  };
}
