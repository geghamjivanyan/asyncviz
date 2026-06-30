/**
 * Keyboard shortcuts for replay navigation.
 *
 * Attaches to a target element (or ``window`` by default) and
 * translates keystrokes into :class:`ReplayControlIntent`s. Modifier
 * keys promote arrow steps to wider jumps:
 *
 *   - Space: play / pause
 *   - ArrowLeft / ArrowRight: step ±1 event
 *   - Shift + ArrowLeft / ArrowRight: previous / next marker
 *   - Ctrl (or Cmd) + ArrowLeft / ArrowRight: previous / next bookmark
 *   - Home / End: jump to start / end
 *   - PageUp / PageDown: jump ±10%
 *   - "." (Period): step forward one frame
 *   - "m": drop a bookmark at the current cursor
 *
 * The mapping is intentionally accessible from a pure helper
 * (``mapKeyToIntent``) so tests can verify every key without DOM
 * setup; the hook itself just wires it to a target.
 */

import { useEffect } from "react";
import {
  jumpByFraction,
  seekToBookmark,
  seekToMarker,
  stepCursor,
} from "@/dashboard/replay/ReplayTimelineSeek";
import { recordKeyboardEvent } from "@/dashboard/replay/diagnostics/ReplayTimelineMetrics";
import { recordReplayTimelineTrace } from "@/dashboard/replay/diagnostics/ReplayTimelineTracing";
import type {
  ReplayBookmark,
  ReplayControlIntent,
  ReplayPlaybackSnapshot,
  ReplaySessionWindow,
  ReplayTimelineMarker,
} from "@/dashboard/replay/models/ReplayTimelineModels";

export interface UseReplayKeyboardOptions {
  readonly enabled?: boolean;
  readonly target?: HTMLElement | Window | null;
  readonly window: ReplaySessionWindow;
  readonly playback: ReplayPlaybackSnapshot;
  readonly markers?: readonly ReplayTimelineMarker[];
  readonly bookmarks?: readonly ReplayBookmark[];
  readonly dispatch: (intent: ReplayControlIntent) => void;
  readonly onBookmark?: (sequence: number) => void;
}

const SMALL_STEP = 1;
const PAGE_FRACTION = 0.1;

export function useReplayKeyboard({
  enabled = true,
  target,
  window: replayWindow,
  playback,
  markers,
  bookmarks,
  dispatch,
  onBookmark,
}: UseReplayKeyboardOptions): void {
  useEffect(() => {
    if (!enabled) return undefined;
    const node: EventTarget = target ?? globalThis.window;

    const handler = (event: Event): void => {
      const keyEvent = event as KeyboardEvent;
      // Don't hijack typing in text fields — replay shortcuts should
      // stay out of the way when the user is searching bookmarks or
      // editing a label.
      const targetEl = keyEvent.target as HTMLElement | null;
      if (targetEl && isEditableTarget(targetEl)) return;

      const intent = mapKeyToIntent(keyEvent, replayWindow, playback, {
        markers,
        bookmarks,
      });
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
  }, [enabled, target, replayWindow, playback, markers, bookmarks, dispatch, onBookmark]);
}

function isEditableTarget(el: HTMLElement): boolean {
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable === true;
}

export interface MapKeyToIntentOptions {
  readonly markers?: readonly ReplayTimelineMarker[];
  readonly bookmarks?: readonly ReplayBookmark[];
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
  options: MapKeyToIntentOptions = {},
): ReplayControlIntent | "bookmark" | null {
  const { key, shiftKey, ctrlKey, metaKey } = event;
  const markerJump = shiftKey && !ctrlKey && !metaKey;
  // Treat Cmd (metaKey) as Ctrl on macOS so the bookmark-jump
  // shortcut feels native on both platforms.
  const bookmarkJump = (ctrlKey || metaKey) && !shiftKey;

  switch (key) {
    case " ":
    case "Spacebar":
      return playback.paused ? { type: "play" } : { type: "pause" };
    case "ArrowLeft":
      if (markerJump) {
        const prev = adjacentMarker(options.markers, playback.lastSequence, "prev");
        return prev !== null ? seekToMarker(prev) : null;
      }
      if (bookmarkJump) {
        const prev = adjacentBookmark(options.bookmarks, playback.lastSequence, "prev");
        return prev !== null ? seekToBookmark(prev) : null;
      }
      return stepCursor(playback.lastSequence, -SMALL_STEP, window);
    case "ArrowRight":
      if (markerJump) {
        const next = adjacentMarker(options.markers, playback.lastSequence, "next");
        return next !== null ? seekToMarker(next) : null;
      }
      if (bookmarkJump) {
        const next = adjacentBookmark(options.bookmarks, playback.lastSequence, "next");
        return next !== null ? seekToBookmark(next) : null;
      }
      return stepCursor(playback.lastSequence, SMALL_STEP, window);
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

function adjacentMarker(
  markers: readonly ReplayTimelineMarker[] | undefined,
  pivot: number,
  direction: "prev" | "next",
): ReplayTimelineMarker | null {
  if (markers === undefined || markers.length === 0) return null;
  let best: ReplayTimelineMarker | null = null;
  for (const m of markers) {
    if (direction === "prev") {
      if (m.sequence < pivot && (best === null || m.sequence > best.sequence)) {
        best = m;
      }
    } else if (m.sequence > pivot && (best === null || m.sequence < best.sequence)) {
      best = m;
    }
  }
  return best;
}

function adjacentBookmark(
  bookmarks: readonly ReplayBookmark[] | undefined,
  pivot: number,
  direction: "prev" | "next",
): ReplayBookmark | null {
  if (bookmarks === undefined || bookmarks.length === 0) return null;
  let best: ReplayBookmark | null = null;
  for (const b of bookmarks) {
    if (direction === "prev") {
      if (b.sequence < pivot && (best === null || b.sequence > best.sequence)) {
        best = b;
      }
    } else if (b.sequence > pivot && (best === null || b.sequence < best.sequence)) {
      best = b;
    }
  }
  return best;
}
