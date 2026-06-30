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
  // Grid sits a tick above the canvas so it suggests rows without
  // competing with segment fills. Minor ≈ 4% lift, major ≈ 8%.
  gridMinor: "#15181f",
  gridMajor: "#1a1f29",
  text: "#d6d9e0",
  muted: "#5f6470",
  subtle: "#3f444e",
  accent: "#60a5fa",
  // Running segments need to pop — bump green saturation; completed
  // segments collapse onto ``muted`` so they recede behind live work.
  success: "#22d36b",
  warning: "#facc15",
  danger: "#fb6a6a",
  selectionFill: "rgba(96,165,250,0.22)",
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
