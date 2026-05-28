/**
 * Selector hooks that read narrow slices of the replay timeline
 * store. Components import these instead of touching the store
 * directly so re-renders are limited to the data each component
 * actually consumes.
 */

import { useReplayTimelineStore } from "@/dashboard/replay/ReplayTimelineStore";
import type {
  ReplayBookmark,
  ReplayPlaybackSnapshot,
  ReplayScrubPhase,
  ReplayScrubPreview,
  ReplaySessionWindow,
  ReplayTimelineMarker,
  ReplayTimelineViewport,
} from "@/dashboard/replay/models/ReplayTimelineModels";

export function useReplayPlayback(): ReplayPlaybackSnapshot {
  return useReplayTimelineStore((s) => s.playback);
}

export function useReplayWindow(): ReplaySessionWindow {
  return useReplayTimelineStore((s) => s.window);
}

export function useReplayViewport(): ReplayTimelineViewport {
  return useReplayTimelineStore((s) => s.viewport);
}

export function useReplayMarkers(): readonly ReplayTimelineMarker[] {
  return useReplayTimelineStore((s) => s.markers);
}

export function useReplayBookmarks(): readonly ReplayBookmark[] {
  return useReplayTimelineStore((s) => s.bookmarks);
}

export function useReplayScrubPhase(): ReplayScrubPhase {
  return useReplayTimelineStore((s) => s.scrubPhase);
}

export function useReplayScrubPreview(): ReplayScrubPreview | null {
  return useReplayTimelineStore((s) => s.scrubPreview);
}

export function useReplayFocusedMarkerId(): string | null {
  return useReplayTimelineStore((s) => s.focusedMarkerId);
}

export function useReplayFocusedBookmarkId(): string | null {
  return useReplayTimelineStore((s) => s.focusedBookmarkId);
}

export function useReplayTimelineStats() {
  return useReplayTimelineStore((s) => s.stats);
}
