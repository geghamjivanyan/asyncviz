/**
 * Zustand store for the replay timeline controls.
 *
 * Owns:
 *   - the current playback snapshot (mirrored from the engine)
 *   - the recording's session window (sequence + timestamp bounds)
 *   - the marker + bookmark inventory
 *   - the live scrub preview while the user drags
 *   - the focused marker / bookmark for keyboard navigation
 *
 * Pure reducer functions live alongside the actions so tests can
 * exercise them without instantiating a Zustand store.
 */

import { create } from "zustand";
import type {
  ReplayBookmark,
  ReplayPlaybackSnapshot,
  ReplayScrubPhase,
  ReplayScrubPreview,
  ReplaySessionWindow,
  ReplayTimelineMarker,
  ReplayTimelineViewport,
} from "@/dashboard/replay/models/ReplayTimelineModels";

export interface ReplayTimelineStats {
  readonly playbackUpdatesApplied: number;
  readonly markersAppended: number;
  readonly bookmarksAdded: number;
  readonly scrubEvents: number;
  readonly seeksRequested: number;
}

const INITIAL_STATS: ReplayTimelineStats = {
  playbackUpdatesApplied: 0,
  markersAppended: 0,
  bookmarksAdded: 0,
  scrubEvents: 0,
  seeksRequested: 0,
};

const INITIAL_PLAYBACK: ReplayPlaybackSnapshot = {
  state: "idle",
  speed: 1,
  lastSequence: 0,
  lastMonotonicNs: 0,
  framesDispatched: 0,
  paused: false,
};

const EMPTY_WINDOW: ReplaySessionWindow = {
  minSequence: 0,
  maxSequence: 0,
  minMonotonicNs: 0,
  maxMonotonicNs: 0,
};

const EMPTY_VIEWPORT: ReplayTimelineViewport = {
  startSequence: 0,
  endSequence: 0,
  widthPx: 0,
};

export interface ReplayTimelineStoreState {
  playback: ReplayPlaybackSnapshot;
  window: ReplaySessionWindow;
  viewport: ReplayTimelineViewport;
  markers: ReplayTimelineMarker[];
  bookmarks: ReplayBookmark[];
  scrubPhase: ReplayScrubPhase;
  scrubPreview: ReplayScrubPreview | null;
  focusedMarkerId: string | null;
  focusedBookmarkId: string | null;
  stats: ReplayTimelineStats;

  setPlayback: (playback: ReplayPlaybackSnapshot) => void;
  setWindow: (window: ReplaySessionWindow) => void;
  setViewport: (viewport: ReplayTimelineViewport) => void;
  setMarkers: (markers: readonly ReplayTimelineMarker[]) => void;
  appendMarker: (marker: ReplayTimelineMarker) => void;
  addBookmark: (bookmark: ReplayBookmark) => void;
  removeBookmark: (bookmarkId: string) => void;
  beginScrub: (preview: ReplayScrubPreview) => void;
  updateScrub: (preview: ReplayScrubPreview) => void;
  endScrub: () => void;
  setFocusedMarker: (id: string | null) => void;
  setFocusedBookmark: (id: string | null) => void;
  recordSeekRequested: () => void;
  reset: () => void;
}

// ── pure reducers ──────────────────────────────────────────────────────

export function reducePlayback(
  state: ReplayTimelineStoreState,
  playback: ReplayPlaybackSnapshot,
): Partial<ReplayTimelineStoreState> {
  return {
    playback,
    stats: {
      ...state.stats,
      playbackUpdatesApplied: state.stats.playbackUpdatesApplied + 1,
    },
  };
}

export function reduceAppendMarker(
  state: ReplayTimelineStoreState,
  marker: ReplayTimelineMarker,
): Partial<ReplayTimelineStoreState> {
  // Keep markers sorted by sequence so projections + nearest-search
  // are cheap.
  const next = [...state.markers, marker].sort(
    (a, b) => a.sequence - b.sequence,
  );
  return {
    markers: next,
    stats: { ...state.stats, markersAppended: state.stats.markersAppended + 1 },
  };
}

export function reduceAddBookmark(
  state: ReplayTimelineStoreState,
  bookmark: ReplayBookmark,
): Partial<ReplayTimelineStoreState> {
  // De-dupe by id.
  const without = state.bookmarks.filter((b) => b.id !== bookmark.id);
  const next = [...without, bookmark].sort((a, b) => a.sequence - b.sequence);
  return {
    bookmarks: next,
    stats: { ...state.stats, bookmarksAdded: state.stats.bookmarksAdded + 1 },
  };
}

export function reduceRemoveBookmark(
  state: ReplayTimelineStoreState,
  bookmarkId: string,
): Partial<ReplayTimelineStoreState> {
  return {
    bookmarks: state.bookmarks.filter((b) => b.id !== bookmarkId),
  };
}

export function reduceBeginScrub(
  state: ReplayTimelineStoreState,
  preview: ReplayScrubPreview,
): Partial<ReplayTimelineStoreState> {
  return {
    scrubPhase: "dragging",
    scrubPreview: preview,
    stats: { ...state.stats, scrubEvents: state.stats.scrubEvents + 1 },
  };
}

export function reduceUpdateScrub(
  state: ReplayTimelineStoreState,
  preview: ReplayScrubPreview,
): Partial<ReplayTimelineStoreState> {
  if (state.scrubPhase !== "dragging") {
    return {};
  }
  return {
    scrubPreview: preview,
    stats: { ...state.stats, scrubEvents: state.stats.scrubEvents + 1 },
  };
}

export function reduceEndScrub(
  state: ReplayTimelineStoreState,
): Partial<ReplayTimelineStoreState> {
  if (state.scrubPhase === "idle") {
    return {};
  }
  return {
    scrubPhase: "idle",
    scrubPreview: null,
  };
}

// ── store implementation ───────────────────────────────────────────────

export const useReplayTimelineStore = create<ReplayTimelineStoreState>(
  (set) => ({
    playback: INITIAL_PLAYBACK,
    window: EMPTY_WINDOW,
    viewport: EMPTY_VIEWPORT,
    markers: [],
    bookmarks: [],
    scrubPhase: "idle",
    scrubPreview: null,
    focusedMarkerId: null,
    focusedBookmarkId: null,
    stats: INITIAL_STATS,

    setPlayback: (playback) => set((s) => reducePlayback(s, playback)),
    setWindow: (window) => set({ window }),
    setViewport: (viewport) => set({ viewport }),
    setMarkers: (markers) =>
      set({
        markers: [...markers].sort((a, b) => a.sequence - b.sequence),
      }),
    appendMarker: (marker) => set((s) => reduceAppendMarker(s, marker)),
    addBookmark: (bookmark) => set((s) => reduceAddBookmark(s, bookmark)),
    removeBookmark: (id) => set((s) => reduceRemoveBookmark(s, id)),
    beginScrub: (preview) => set((s) => reduceBeginScrub(s, preview)),
    updateScrub: (preview) => set((s) => reduceUpdateScrub(s, preview)),
    endScrub: () => set((s) => reduceEndScrub(s)),
    setFocusedMarker: (id) => set({ focusedMarkerId: id }),
    setFocusedBookmark: (id) => set({ focusedBookmarkId: id }),
    recordSeekRequested: () =>
      set((s) => ({
        stats: { ...s.stats, seeksRequested: s.stats.seeksRequested + 1 },
      })),
    reset: () =>
      set({
        playback: INITIAL_PLAYBACK,
        window: EMPTY_WINDOW,
        viewport: EMPTY_VIEWPORT,
        markers: [],
        bookmarks: [],
        scrubPhase: "idle",
        scrubPreview: null,
        focusedMarkerId: null,
        focusedBookmarkId: null,
        stats: INITIAL_STATS,
      }),
  }),
);

// ── initial-state factory for unit tests ───────────────────────────────

export function initialReplayTimelineState(): ReplayTimelineStoreState {
  // The Zustand action methods are never called from reducer tests,
  // so we stub them with no-ops to keep the type strict.
  const noop = () => undefined;
  return {
    playback: INITIAL_PLAYBACK,
    window: EMPTY_WINDOW,
    viewport: EMPTY_VIEWPORT,
    markers: [],
    bookmarks: [],
    scrubPhase: "idle",
    scrubPreview: null,
    focusedMarkerId: null,
    focusedBookmarkId: null,
    stats: INITIAL_STATS,
    setPlayback: noop,
    setWindow: noop,
    setViewport: noop,
    setMarkers: noop,
    appendMarker: noop,
    addBookmark: noop,
    removeBookmark: noop,
    beginScrub: noop,
    updateScrub: noop,
    endScrub: noop,
    setFocusedMarker: noop,
    setFocusedBookmark: noop,
    recordSeekRequested: noop,
    reset: noop,
  };
}
