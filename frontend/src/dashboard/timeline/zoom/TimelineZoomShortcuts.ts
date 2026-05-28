/**
 * Pure key-binding model for the zoom controller.
 *
 * The bindings encode platform-aware key combos (``Ctrl`` on Linux /
 * Windows, ``Meta`` on macOS) + their semantic action. The React
 * adapter (``useTimelineZoomShortcuts``) binds them to the DOM.
 *
 * Keeping the data model separate from the binding lets us emit the
 * same shortcuts in the toolbar tooltips, the diagnostics dump, and
 * the future settings UI without duplication.
 */

export type ZoomShortcutAction =
  | "zoom-in"
  | "zoom-out"
  | "zoom-reset"
  | "fit-all";

export interface ZoomShortcutBinding {
  action: ZoomShortcutAction;
  /** Display label shown in tooltips / docs. */
  label: string;
  /** Keys participate in match — case-insensitive. */
  key: string;
  /** Whether the binding requires the platform modifier (Ctrl/Cmd). */
  requiresPlatformModifier: boolean;
  /** Whether the binding requires Shift. */
  shift: boolean;
}

export const DEFAULT_ZOOM_SHORTCUTS: readonly ZoomShortcutBinding[] = Object.freeze([
  {
    action: "zoom-in",
    label: "Cmd/Ctrl + =",
    key: "=",
    requiresPlatformModifier: true,
    shift: false,
  },
  {
    action: "zoom-in",
    label: "Cmd/Ctrl + +",
    key: "+",
    requiresPlatformModifier: true,
    shift: false,
  },
  {
    action: "zoom-out",
    label: "Cmd/Ctrl + -",
    key: "-",
    requiresPlatformModifier: true,
    shift: false,
  },
  {
    action: "zoom-reset",
    label: "Cmd/Ctrl + 0",
    key: "0",
    requiresPlatformModifier: true,
    shift: false,
  },
  {
    action: "fit-all",
    label: "Cmd/Ctrl + 9",
    key: "9",
    requiresPlatformModifier: true,
    shift: false,
  },
]);

export interface KeyboardEventLike {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  shiftKey?: boolean;
}

/** Pure: ``true`` when ``event`` carries the platform modifier (Ctrl
 *  on Linux/Win, Meta on macOS). */
export function hasPlatformModifier(event: KeyboardEventLike): boolean {
  return Boolean(event.ctrlKey || event.metaKey);
}

/** Pure: match an event against the binding list and return the
 *  matched action (if any). */
export function matchShortcut(
  event: KeyboardEventLike,
  bindings: readonly ZoomShortcutBinding[] = DEFAULT_ZOOM_SHORTCUTS,
): ZoomShortcutAction | null {
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
