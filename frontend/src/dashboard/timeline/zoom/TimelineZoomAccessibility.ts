/**
 * Helpers that build screen-reader-friendly announcements for the
 * zoom controller.
 *
 * The dashboard mounts a single ``role="status"`` live region that
 * mirrors zoom state changes. These helpers return the strings the
 * region should render — keeping the formatting decisions in one
 * place means assistive tooling sees identical messages whether the
 * change came from the toolbar, a shortcut, or a preset.
 */

import type { TimelineZoomState } from "@/dashboard/timeline/zoom/models/TimelineZoomModels";

/** Pure: build a concise human-readable announcement for a zoom
 *  state. */
export function describeZoomState(state: TimelineZoomState): string {
  const duration = formatDuration(state.durationSeconds);
  const percent = `${Math.round(state.level * 100)}%`;
  const edge = state.atMin
    ? " (at minimum zoom)"
    : state.atMax
      ? " (at maximum zoom)"
      : "";
  return `Visible duration ${duration}, zoom level ${percent}${edge}.`;
}

/** Pure: build an announcement for a zoom action ("Zoomed in", etc.). */
export function describeZoomAction(action: "zoom-in" | "zoom-out" | "zoom-reset" | "fit-all"): string {
  switch (action) {
    case "zoom-in":
      return "Zoomed in.";
    case "zoom-out":
      return "Zoomed out.";
    case "zoom-reset":
      return "Zoom reset.";
    case "fit-all":
      return "Fit timeline to data.";
  }
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "0s";
  if (seconds < 1e-3) return `${(seconds * 1e6).toFixed(0)}µs`;
  if (seconds < 1) return `${(seconds * 1e3).toFixed(1)}ms`;
  if (seconds < 60) return `${seconds.toFixed(2)}s`;
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${minutes}m${secs.toFixed(0).padStart(2, "0")}s`;
}
