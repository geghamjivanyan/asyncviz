/**
 * Engine bridge contract.
 *
 * The replay UI doesn't import the backend engine directly — instead
 * it speaks against this small adapter protocol. A real binding
 * (websocket-backed, polling, etc.) lives elsewhere; tests + the
 * default dashboard wiring supply lightweight in-process bridges.
 */

import type {
  ReplayBookmark,
  ReplayControlIntent,
  ReplayPlaybackSnapshot,
  ReplaySessionWindow,
  ReplayTimelineMarker,
} from "@/dashboard/replay/models/ReplayTimelineModels";

/** Subscription handle returned by every ``subscribe*`` method. */
export type ReplayEngineUnsubscribe = () => void;

/** Adapter the controls require — a small surface so it's easy to
 *  mock in tests and easy to wire to a websocket / REST source. */
export interface ReplayEngineBridge {
  /** Latest known session window. */
  getSessionWindow(): ReplaySessionWindow;
  /** Latest known playback snapshot. */
  getPlaybackSnapshot(): ReplayPlaybackSnapshot;
  /** Subscribe to playback snapshot updates. Fires on every change. */
  subscribePlayback(
    listener: (snapshot: ReplayPlaybackSnapshot) => void,
  ): ReplayEngineUnsubscribe;
  /** Subscribe to incoming markers (e.g. from a websocket stream). */
  subscribeMarkers(
    listener: (marker: ReplayTimelineMarker) => void,
  ): ReplayEngineUnsubscribe;
  /** Subscribe to bookmark mutations (added/removed/renamed). */
  subscribeBookmarks(
    listener: (bookmarks: readonly ReplayBookmark[]) => void,
  ): ReplayEngineUnsubscribe;
  /** Dispatch a control intent — engine bridge translates this into
   *  a real call. */
  dispatch(intent: ReplayControlIntent): void | Promise<void>;
}

/** Lightweight in-process bridge — useful for tests + the static
 *  diagnostics preview. */
export class InMemoryReplayEngineBridge implements ReplayEngineBridge {
  private window: ReplaySessionWindow = {
    minSequence: 0,
    maxSequence: 0,
    minMonotonicNs: 0,
    maxMonotonicNs: 0,
  };
  private playback: ReplayPlaybackSnapshot = {
    state: "idle",
    speed: 1,
    lastSequence: 0,
    lastMonotonicNs: 0,
    framesDispatched: 0,
    paused: false,
  };
  private bookmarks: ReplayBookmark[] = [];
  private playbackListeners = new Set<
    (snapshot: ReplayPlaybackSnapshot) => void
  >();
  private markerListeners = new Set<
    (marker: ReplayTimelineMarker) => void
  >();
  private bookmarkListeners = new Set<
    (bookmarks: readonly ReplayBookmark[]) => void
  >();
  readonly intents: ReplayControlIntent[] = [];

  getSessionWindow(): ReplaySessionWindow {
    return this.window;
  }

  getPlaybackSnapshot(): ReplayPlaybackSnapshot {
    return this.playback;
  }

  setSessionWindow(window: ReplaySessionWindow): void {
    this.window = window;
  }

  setPlayback(snapshot: ReplayPlaybackSnapshot): void {
    this.playback = snapshot;
    this.playbackListeners.forEach((listener) => listener(snapshot));
  }

  emitMarker(marker: ReplayTimelineMarker): void {
    this.markerListeners.forEach((listener) => listener(marker));
  }

  setBookmarks(bookmarks: readonly ReplayBookmark[]): void {
    this.bookmarks = bookmarks.slice();
    this.bookmarkListeners.forEach((listener) => listener(this.bookmarks));
  }

  subscribePlayback(
    listener: (snapshot: ReplayPlaybackSnapshot) => void,
  ): ReplayEngineUnsubscribe {
    this.playbackListeners.add(listener);
    return () => this.playbackListeners.delete(listener);
  }

  subscribeMarkers(
    listener: (marker: ReplayTimelineMarker) => void,
  ): ReplayEngineUnsubscribe {
    this.markerListeners.add(listener);
    return () => this.markerListeners.delete(listener);
  }

  subscribeBookmarks(
    listener: (bookmarks: readonly ReplayBookmark[]) => void,
  ): ReplayEngineUnsubscribe {
    this.bookmarkListeners.add(listener);
    return () => this.bookmarkListeners.delete(listener);
  }

  dispatch(intent: ReplayControlIntent): void {
    this.intents.push(intent);
  }
}
