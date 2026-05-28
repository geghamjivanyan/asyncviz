/**
 * Canonical type models for the replay timeline controls.
 *
 * These types describe what the UI thinks of as a "replay session"
 * — the engine's playback snapshot, the recording's sequence/timestamp
 * span, marker overlays, bookmarks, and the various transient cursors
 * the controls render (playhead, scrub preview, focus).
 *
 * Keep these types small + serializable. The replay controls receive
 * them from the engine bridge as plain JSON objects and pass them
 * straight into Zustand without further translation.
 */

/** Discrete states the engine reports back to the UI. */
export type ReplayPlaybackState =
  | "idle"
  | "playing"
  | "paused"
  | "seeking"
  | "buffering"
  | "stopped"
  | "failed";

/** Severity of a timeline marker — drives colour + screen-reader text. */
export type ReplayMarkerSeverity = "info" | "warning" | "critical";

/** Kind of marker — describes which subsystem produced it. */
export type ReplayMarkerKind =
  | "warning"
  | "saturation"
  | "blocking"
  | "checkpoint"
  | "bookmark"
  | "annotation";

/** Span of a recording exposed to the controls. */
export interface ReplaySessionWindow {
  /** Inclusive lower bound. ``1`` for a fresh recording. */
  readonly minSequence: number;
  /** Inclusive upper bound. ``0`` when the recording is empty. */
  readonly maxSequence: number;
  /** Earliest ``monotonic_ns`` observed in the recording. */
  readonly minMonotonicNs: number;
  /** Latest ``monotonic_ns`` observed. */
  readonly maxMonotonicNs: number;
}

/** What the engine reports about the current playback position. */
export interface ReplayPlaybackSnapshot {
  readonly state: ReplayPlaybackState;
  readonly speed: number;
  readonly lastSequence: number;
  readonly lastMonotonicNs: number;
  readonly framesDispatched: number;
  readonly paused: boolean;
  readonly errorDetail?: string;
}

/** One timeline marker — placed in sequence + timestamp space. */
export interface ReplayTimelineMarker {
  readonly id: string;
  readonly kind: ReplayMarkerKind;
  readonly severity: ReplayMarkerSeverity;
  readonly sequence: number;
  readonly monotonicNs: number;
  readonly label: string;
  readonly description?: string;
}

/** User-defined bookmark — same shape as a marker but persists across sessions. */
export interface ReplayBookmark {
  readonly id: string;
  readonly label: string;
  readonly sequence: number;
  readonly monotonicNs: number;
  readonly note?: string;
  readonly createdAtMs: number;
}

/** Transient scrub cursor — produced while the user drags the playhead. */
export interface ReplayScrubPreview {
  readonly sequence: number;
  readonly monotonicNs: number;
  readonly clientX: number;
  readonly normalizedFraction: number;
}

/** Snapshot of the controls' viewport (visible sequence range). */
export interface ReplayTimelineViewport {
  readonly startSequence: number;
  readonly endSequence: number;
  readonly widthPx: number;
}

/** Discrete control intents the controls bubble up to the engine bridge. */
export type ReplayControlIntent =
  | { type: "play" }
  | { type: "pause" }
  | { type: "stop" }
  | { type: "step-forward" }
  | { type: "set-speed"; speed: number }
  | { type: "seek-sequence"; sequence: number }
  | { type: "seek-timestamp"; monotonicNs: number }
  | { type: "jump-to-bookmark"; bookmarkId: string };

/** Drag lifecycle phase for the scrubber. */
export type ReplayScrubPhase = "idle" | "dragging" | "settling";

/** Mini-map sampling bucket. */
export interface ReplayTimelineBucket {
  readonly startSequence: number;
  readonly endSequence: number;
  /** Number of markers (any kind) that fall in this bucket. */
  readonly markerCount: number;
  readonly severityCount: Readonly<Record<ReplayMarkerSeverity, number>>;
}
