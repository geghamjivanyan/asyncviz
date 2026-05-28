/**
 * Keyboard shortcuts for replay navigation.
 *
 * Attaches to a target element (or ``window`` by default) and
 * translates keystrokes into :class:`ReplayControlIntent`s. The
 * keymap matches what the brief asked for:
 *
 *   - Space: play / pause
 *   - ArrowLeft / ArrowRight: step ±1 frame
 *   - Shift + ArrowLeft / ArrowRight: jump ±5%
 *   - Home / End: jump to start / end
 *   - PageUp / PageDown: jump ±10%
 *   - "." (Period): step forward one frame
 *   - "m": drop a bookmark at the current cursor
 */

import { useEffect } from "react";
import {
  jumpByFraction,
  stepCursor,
} from "@/dashboard/replay/ReplayTimelineSeek";
import {
  recordKeyboardEvent,
} from "@/dashboard/replay/diagnostics/ReplayTimelineMetrics";
import {
  recordReplayTimelineTrace,
} from "@/dashboard/replay/diagnostics/ReplayTimelineTracing";
import type { ReplayControlIntent } from "@/dashboard/replay/models/ReplayTimelineModels";
import type {
  ReplayPlaybackSnapshot,
  ReplaySessionWindow,
} from "@/dashboard/replay/models/ReplayTimelineModels";

export interface UseReplayKeyboardOptions {
  readonly enabled?: boolean;
  readonly target?: HTMLElement | Window | null;
  readonly window: ReplaySessionWindow;
  readonly playback: ReplayPlaybackSnapshot;
  readonly dispatch: (intent: ReplayControlIntent) => void;
  readonly onBookmark?: (sequence: number) => void;
}

const SMALL_STEP = 1;
const SHIFT_FRACTION = 0.05;
const PAGE_FRACTION = 0.1;

export function useReplayKeyboard({
  enabled = true,
  target,
  window: replayWindow,
  playback,
  dispatch,
  onBookmark,
}: UseReplayKeyboardOptions): void {
  useEffect(() => {
    if (!enabled) return undefined;
    const node: EventTarget = target ?? globalThis.window;

    const handler = (event: Event): void => {
      const keyEvent = event as KeyboardEvent;
      const intent = mapKeyToIntent(keyEvent, replayWindow, playback);
      if (intent === "bookmark") {
        recordKeyboardEvent();
        recordReplayTimelineTrace("keyboard", "bookmark");
        onBookmark?.(playback.lastSequence);
        keyEvent.preventDefault();
        return;
      }
      if (intent !== null) {
        recordKeyboardEvent();
        recordReplayTimelineTrace("keyboard", keyEvent.key);
        dispatch(intent);
        keyEvent.preventDefault();
      }
    };
    node.addEventListener("keydown", handler);
    return () => node.removeEventListener("keydown", handler);
  }, [enabled, target, replayWindow, playback, dispatch, onBookmark]);
}

/**
 * Pure-function key → intent mapping. Exposed for tests so each
 * keystroke can be verified without spinning up the DOM.
 *
 * Returns ``"bookmark"`` for the bookmark shortcut so the caller can
 * route it to a side-effect (not a control intent).
 */
export function mapKeyToIntent(
  event: KeyboardEvent,
  window: ReplaySessionWindow,
  playback: ReplayPlaybackSnapshot,
): ReplayControlIntent | "bookmark" | null {
  const { key, shiftKey } = event;
  switch (key) {
    case " ":
    case "Spacebar":
      return playback.paused ? { type: "play" } : { type: "pause" };
    case "ArrowLeft":
      return shiftKey
        ? jumpByFraction(playback.lastSequence, -SHIFT_FRACTION, window)
        : stepCursor(playback.lastSequence, -SMALL_STEP, window);
    case "ArrowRight":
      return shiftKey
        ? jumpByFraction(playback.lastSequence, SHIFT_FRACTION, window)
        : stepCursor(playback.lastSequence, SMALL_STEP, window);
    case "Home":
      return { type: "seek-sequence", sequence: window.minSequence };
    case "End":
      return { type: "seek-sequence", sequence: window.maxSequence };
    case "PageUp":
      return jumpByFraction(playback.lastSequence, -PAGE_FRACTION, window);
    case "PageDown":
      return jumpByFraction(playback.lastSequence, PAGE_FRACTION, window);
    case ".":
      return { type: "step-forward" };
    case "m":
    case "M":
      return "bookmark";
    default:
      return null;
  }
}
