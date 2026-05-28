/**
 * Canonical color palette for canvas drawing.
 *
 * The dashboard's design tokens live in CSS custom properties; the
 * renderer needs literal color strings so it doesn't read the
 * computed style every frame. The palette here intentionally mirrors
 * the Tailwind ``@theme`` block in ``src/styles/index.css``.
 */

export interface TimelineColorPalette {
  background: string;
  canvas: string;
  line: string;
  gridMinor: string;
  gridMajor: string;
  text: string;
  muted: string;
  subtle: string;
  accent: string;
  success: string;
  warning: string;
  danger: string;
  selectionFill: string;
  selectionStroke: string;
  overlayCursor: string;
}

export const DEFAULT_TIMELINE_PALETTE: TimelineColorPalette = {
  background: "#0b0d10",
  canvas: "#12151b",
  line: "#1f2430",
  gridMinor: "#181c24",
  gridMajor: "#1f2430",
  text: "#d6d9e0",
  muted: "#7d828c",
  subtle: "#4f545e",
  accent: "#60a5fa",
  success: "#4ade80",
  warning: "#facc15",
  danger: "#f87171",
  selectionFill: "rgba(96,165,250,0.18)",
  selectionStroke: "#60a5fa",
  overlayCursor: "rgba(214,217,224,0.32)",
};

/** Pure: map a segment intent to a fill color. */
export function segmentFill(
  palette: TimelineColorPalette,
  intent: "default" | "run" | "wait" | "completed" | "cancelled" | "failed",
): string {
  switch (intent) {
    case "run":
      return palette.success;
    case "wait":
      return palette.warning;
    case "completed":
      return palette.muted;
    case "cancelled":
      return palette.warning;
    case "failed":
      return palette.danger;
    default:
      return palette.accent;
  }
}
