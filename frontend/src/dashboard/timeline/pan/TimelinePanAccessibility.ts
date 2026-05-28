/**
 * Pure helpers that format screen-reader announcements for pan state.
 */

import type { TimelinePanState } from "@/dashboard/timeline/pan/models/TimelinePanModels";

/** Pure: build a concise human-readable announcement for a pan state. */
export function describePanState(state: TimelinePanState): string {
  const start = formatTime(state.timeStartSeconds);
  const end = formatTime(state.timeEndSeconds);
  const edge = state.atMinTime
    ? " (at start of timeline)"
    : state.atMaxTime
      ? " (at end of timeline)"
      : "";
  return `Visible range ${start}–${end}${edge}.`;
}

/** Pure: build an announcement for a pan action. */
export function describePanAction(
  action:
    | "pan-left"
    | "pan-right"
    | "pan-left-fast"
    | "pan-right-fast"
    | "pan-home"
    | "pan-end"
    | "center"
    | "to-time",
): string {
  switch (action) {
    case "pan-left":
      return "Panned left.";
    case "pan-right":
      return "Panned right.";
    case "pan-left-fast":
      return "Panned left fast.";
    case "pan-right-fast":
      return "Panned right fast.";
    case "pan-home":
      return "Jumped to start.";
    case "pan-end":
      return "Jumped to end.";
    case "center":
      return "Centered on selection.";
    case "to-time":
      return "Moved viewport.";
  }
}

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds)) return "—";
  if (Math.abs(seconds) < 1) return `${(seconds * 1000).toFixed(0)}ms`;
  if (Math.abs(seconds) < 60) return `${seconds.toFixed(2)}s`;
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${minutes}m${secs.toFixed(0).padStart(2, "0")}s`;
}
