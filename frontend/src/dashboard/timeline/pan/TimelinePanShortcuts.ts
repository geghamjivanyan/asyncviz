/**
 * Pure key-binding model for the pan controller.
 */

export type PanShortcutAction =
  | "pan-left"
  | "pan-right"
  | "pan-left-fast"
  | "pan-right-fast"
  | "pan-home"
  | "pan-end";

export interface PanShortcutBinding {
  action: PanShortcutAction;
  label: string;
  key: string;
  /** When set, the binding requires the platform modifier (Ctrl/Cmd). */
  requiresPlatformModifier: boolean;
  /** When set, the binding requires Shift. */
  shift: boolean;
}

export const DEFAULT_PAN_SHORTCUTS: readonly PanShortcutBinding[] = Object.freeze([
  {
    action: "pan-left",
    label: "ArrowLeft",
    key: "arrowleft",
    requiresPlatformModifier: false,
    shift: false,
  },
  {
    action: "pan-right",
    label: "ArrowRight",
    key: "arrowright",
    requiresPlatformModifier: false,
    shift: false,
  },
  {
    action: "pan-left-fast",
    label: "Shift + ArrowLeft",
    key: "arrowleft",
    requiresPlatformModifier: false,
    shift: true,
  },
  {
    action: "pan-right-fast",
    label: "Shift + ArrowRight",
    key: "arrowright",
    requiresPlatformModifier: false,
    shift: true,
  },
  {
    action: "pan-home",
    label: "Home",
    key: "home",
    requiresPlatformModifier: false,
    shift: false,
  },
  {
    action: "pan-end",
    label: "End",
    key: "end",
    requiresPlatformModifier: false,
    shift: false,
  },
]);

export interface KeyboardEventLike {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  shiftKey?: boolean;
}

export function hasPlatformModifier(event: KeyboardEventLike): boolean {
  return Boolean(event.ctrlKey || event.metaKey);
}

/** Pure: match an event against the binding list. */
export function matchPanShortcut(
  event: KeyboardEventLike,
  bindings: readonly PanShortcutBinding[] = DEFAULT_PAN_SHORTCUTS,
): PanShortcutAction | null {
  const key = event.key.toLowerCase();
  const shift = Boolean(event.shiftKey);
  const platformMod = hasPlatformModifier(event);
  for (const binding of bindings) {
    if (binding.key.toLowerCase() !== key) continue;
    if (binding.requiresPlatformModifier !== platformMod) continue;
    if (binding.shift !== shift) continue;
    return binding.action;
  }
  return null;
}
