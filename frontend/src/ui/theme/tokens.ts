/**
 * Design tokens consumed by the UI primitives.
 *
 * Colors / spacing / typography are owned by the Tailwind 4 ``@theme``
 * block in ``src/styles/index.css``; this module names the abstractions
 * so component props (``intent="success"``, ``padding="md"``) can map
 * to the right Tailwind class without scattering string literals.
 */

export const PALETTE = {
  canvas: "bg-canvas",
  panel: "bg-panel",
  elevated: "bg-elevated",
  accent: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
} as const;

export const TEXT_PALETTE = {
  text: "text-text",
  muted: "text-muted",
  subtle: "text-subtle",
  accent: "text-accent",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
} as const;

export const INTENT_BORDER = {
  default: "border-line",
  accent: "border-accent",
  success: "border-success",
  warning: "border-warning",
  danger: "border-danger",
} as const;

export type Intent = keyof typeof INTENT_BORDER;

export const SPACING = {
  none: "p-0",
  xs: "p-1",
  sm: "p-2",
  md: "p-3",
  lg: "p-4",
  xl: "p-6",
} as const;

export type Spacing = keyof typeof SPACING;
