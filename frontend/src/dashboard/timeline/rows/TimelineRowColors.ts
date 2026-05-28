/**
 * Canonical row → palette mapping.
 *
 * Centralises every color decision the row renderer makes so layers
 * never re-derive palette colors themselves. Keeps colors deterministic
 * and easy to reskin via :type:`TimelineColorPalette` overrides.
 */

import type { TimelineColorPalette } from "@/dashboard/timeline/rendering/TimelineColors";
import type {
  TimelineRowState,
  TimelineRowWarningSeverity,
} from "@/dashboard/timeline/rendering/TimelineLayer";

/** Background fill for a row at rest. */
export function rowBackgroundFill(palette: TimelineColorPalette, state: TimelineRowState): string {
  switch (state) {
    case "running":
      return withAlpha(palette.success, 0.06);
    case "waiting":
      return withAlpha(palette.warning, 0.06);
    case "completed":
      return withAlpha(palette.muted, 0.05);
    case "cancelled":
      return withAlpha(palette.warning, 0.09);
    case "failed":
      return withAlpha(palette.danger, 0.1);
    case "created":
      return withAlpha(palette.accent, 0.04);
    default:
      return "transparent";
  }
}

/** Row separator stroke. */
export function rowSeparatorStroke(palette: TimelineColorPalette): string {
  return palette.gridMinor;
}

/** Row state-indicator bar (state pill on the leading edge). */
export function rowStateIndicator(palette: TimelineColorPalette, state: TimelineRowState): string {
  switch (state) {
    case "running":
      return palette.success;
    case "waiting":
      return palette.warning;
    case "completed":
      return palette.muted;
    case "cancelled":
      return palette.warning;
    case "failed":
      return palette.danger;
    case "created":
      return palette.accent;
    default:
      return palette.subtle;
  }
}

/** Background tint to overlay when the row carries an active warning. */
export function rowWarningTint(
  palette: TimelineColorPalette,
  severity: TimelineRowWarningSeverity,
): string {
  switch (severity) {
    case "critical":
      return withAlpha(palette.danger, 0.15);
    case "error":
      return withAlpha(palette.danger, 0.1);
    case "warning":
      return withAlpha(palette.warning, 0.1);
    case "info":
      return withAlpha(palette.accent, 0.08);
  }
}

/** Warning chip outline / glyph color. */
export function rowWarningStroke(
  palette: TimelineColorPalette,
  severity: TimelineRowWarningSeverity,
): string {
  switch (severity) {
    case "critical":
    case "error":
      return palette.danger;
    case "warning":
      return palette.warning;
    case "info":
      return palette.accent;
  }
}

/** Selection background fill. */
export function rowSelectionFill(palette: TimelineColorPalette): string {
  return palette.selectionFill;
}

/** Selection stroke. */
export function rowSelectionStroke(palette: TimelineColorPalette): string {
  return palette.selectionStroke;
}

/** Replay highlight fill — distinct from selection so they can stack. */
export function rowReplayFill(palette: TimelineColorPalette): string {
  return withAlpha(palette.accent, 0.08);
}

/** Replay highlight stroke. */
export function rowReplayStroke(palette: TimelineColorPalette): string {
  return palette.accent;
}

/** Label color. */
export function rowLabelText(palette: TimelineColorPalette): string {
  return palette.text;
}

/** Secondary label color (coroutine, badges). */
export function rowSecondaryText(palette: TimelineColorPalette): string {
  return palette.muted;
}

// ── helpers ─────────────────────────────────────────────────────────

/** Apply an alpha channel to a hex / rgb color. Pure + defensive. */
export function withAlpha(color: string, alpha: number): string {
  const a = Math.max(0, Math.min(1, alpha));
  if (color.startsWith("#")) {
    const { r, g, b } = parseHex(color);
    return `rgba(${r}, ${g}, ${b}, ${a})`;
  }
  if (color.startsWith("rgba(")) return color;
  if (color.startsWith("rgb(")) {
    const trimmed = color.slice(4, -1);
    return `rgba(${trimmed}, ${a})`;
  }
  return color;
}

function parseHex(value: string): { r: number; g: number; b: number } {
  let body = value.slice(1);
  if (body.length === 3) {
    body = body
      .split("")
      .map((c) => c + c)
      .join("");
  }
  if (body.length !== 6) return { r: 0, g: 0, b: 0 };
  const r = parseInt(body.slice(0, 2), 16);
  const g = parseInt(body.slice(2, 4), 16);
  const b = parseInt(body.slice(4, 6), 16);
  return {
    r: Number.isFinite(r) ? r : 0,
    g: Number.isFinite(g) ? g : 0,
    b: Number.isFinite(b) ? b : 0,
  };
}
