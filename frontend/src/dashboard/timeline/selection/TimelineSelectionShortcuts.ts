/**
 * Pure key-binding model for the selection controller.
 */

export type SelectionShortcutAction =
  | "select-next"
  | "select-previous"
  | "select-first"
  | "select-last"
  | "clear-selection"
  | "center-selection"
  | "reveal-selection";

export interface SelectionShortcutBinding {
  action: SelectionShortcutAction;
  label: string;
  key: string;
  /** Require the platform modifier (Ctrl/Cmd). */
  requiresPlatformModifier: boolean;
  /** Require Shift. */
  shift: boolean;
  /** Require Alt. */
  alt: boolean;
}

export const DEFAULT_SELECTION_SHORTCUTS: readonly SelectionShortcutBinding[] = Object.freeze([
  {
    action: "select-next",
    label: "ArrowDown",
    key: "arrowdown",
    requiresPlatformModifier: false,
    shift: false,
    alt: false,
  },
  {
    action: "select-previous",
    label: "ArrowUp",
    key: "arrowup",
    requiresPlatformModifier: false,
    shift: false,
    alt: false,
  },
  {
    action: "select-first",
    label: "Shift + Home",
    key: "home",
    requiresPlatformModifier: false,
    shift: true,
    alt: false,
  },
  {
    action: "select-last",
    label: "Shift + End",
    key: "end",
    requiresPlatformModifier: false,
    shift: true,
    alt: false,
  },
  {
    action: "clear-selection",
    label: "Escape",
    key: "escape",
    requiresPlatformModifier: false,
    shift: false,
    alt: false,
  },
  {
    action: "center-selection",
    label: "F",
    key: "f",
    requiresPlatformModifier: false,
    shift: false,
    alt: false,
  },
  {
    action: "reveal-selection",
    label: "R",
    key: "r",
    requiresPlatformModifier: false,
    shift: false,
    alt: false,
  },
]);

export interface KeyboardEventLike {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  shiftKey?: boolean;
  altKey?: boolean;
}

export function hasPlatformModifier(event: KeyboardEventLike): boolean {
  return Boolean(event.ctrlKey || event.metaKey);
}

/** Pure: match an event against the binding list. */
export function matchSelectionShortcut(
  event: KeyboardEventLike,
  bindings: readonly SelectionShortcutBinding[] = DEFAULT_SELECTION_SHORTCUTS,
): SelectionShortcutAction | null {
  const key = event.key.toLowerCase();
  const shift = Boolean(event.shiftKey);
  const alt = Boolean(event.altKey);
  const platformMod = hasPlatformModifier(event);
  for (const binding of bindings) {
    if (binding.key.toLowerCase() !== key) continue;
    if (binding.requiresPlatformModifier !== platformMod) continue;
    if (binding.shift !== shift) continue;
    if (binding.alt !== alt) continue;
    return binding.action;
  }
  return null;
}
