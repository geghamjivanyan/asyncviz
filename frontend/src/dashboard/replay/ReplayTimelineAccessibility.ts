/**
 * Accessibility text helpers.
 *
 * Screen readers get one consistent surface across every control:
 *   - the playback summary ("Playing, 2x speed, frame 4321 of 9000")
 *   - per-marker labels ("Critical saturation marker at frame 2103")
 *   - per-bookmark labels
 *   - keystroke help ("Press Space to play. Use arrow keys to seek")
 *
 * Keeping the strings here means they're easy to verify in tests
 * and easy to localize later without touching the components.
 */

import {
  sequenceToFraction,
} from "@/dashboard/replay/ReplayTimelineGeometry";
import type {
  ReplayBookmark,
  ReplayPlaybackSnapshot,
  ReplaySessionWindow,
  ReplayTimelineMarker,
} from "@/dashboard/replay/models/ReplayTimelineModels";

/** Render a playback snapshot into a screen-reader-friendly
 *  one-line summary. */
export function describePlaybackForAccessibility(
  playback: ReplayPlaybackSnapshot,
  window: ReplaySessionWindow,
): string {
  const stateText = playback.state.charAt(0).toUpperCase() + playback.state.slice(1);
  const speedText = `${playback.speed.toFixed(2)}x speed`;
  const positionText =
    window.maxSequence > 0
      ? `frame ${playback.lastSequence} of ${window.maxSequence}`
      : "no recording loaded";
  return `${stateText}, ${speedText}, ${positionText}.`;
}

/** Describe one marker. */
export function describeMarkerForAccessibility(
  marker: ReplayTimelineMarker,
  window: ReplaySessionWindow,
): string {
  const fraction = Math.round(sequenceToFraction(marker.sequence, window) * 100);
  const severity =
    marker.severity.charAt(0).toUpperCase() + marker.severity.slice(1);
  const base = `${severity} ${marker.kind} marker at frame ${marker.sequence} (${fraction}% through recording).`;
  return marker.description ? `${base} ${marker.description}` : base;
}

/** Describe one bookmark. */
export function describeBookmarkForAccessibility(
  bookmark: ReplayBookmark,
  window: ReplaySessionWindow,
): string {
  const fraction = Math.round(
    sequenceToFraction(bookmark.sequence, window) * 100,
  );
  const base = `Bookmark "${bookmark.label}" at frame ${bookmark.sequence} (${fraction}% through recording).`;
  return bookmark.note ? `${base} ${bookmark.note}` : base;
}

/** Stable help text for keyboard interaction — appended to the
 *  scrubber's ``aria-describedby`` element. */
export const REPLAY_KEYBOARD_HELP =
  "Space to play or pause. Arrow keys to step. Shift plus arrow keys to jump by 5%. " +
  "Home and End to jump to start or end. M to drop a bookmark. Period to step one frame.";

/** Announce a scrub-end / seek-completed event via an aria-live
 *  region. The result is a short sentence; the live region pushes
 *  it to screen readers automatically. */
export function announceSeekCompleted(
  sequence: number,
  window: ReplaySessionWindow,
): string {
  if (window.maxSequence === 0) return "Replay is empty.";
  const fraction = Math.round(sequenceToFraction(sequence, window) * 100);
  return `Replay positioned at frame ${sequence}, ${fraction}% through recording.`;
}

/** Announce a state transition. */
export function announceStateTransition(
  previous: ReplayPlaybackSnapshot,
  next: ReplayPlaybackSnapshot,
): string | null {
  if (previous.state === next.state && previous.speed === next.speed) {
    return null;
  }
  if (previous.state !== next.state) {
    return `Replay ${next.state}.`;
  }
  return `Replay speed set to ${next.speed.toFixed(2)}x.`;
}
