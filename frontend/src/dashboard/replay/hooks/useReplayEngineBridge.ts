/**
 * Connect a :class:`ReplayEngineBridge` to the store.
 *
 * Subscribes to playback / marker / bookmark streams and mirrors
 * them into the Zustand store so every component selector sees the
 * same data. Unmount cleans up subscriptions.
 */

import { useEffect } from "react";
import type { ReplayEngineBridge } from "@/dashboard/replay/hooks/ReplayEngineBridge";
import { useReplayTimelineStore } from "@/dashboard/replay/ReplayTimelineStore";
import {
  recordReplayTimelineTrace,
} from "@/dashboard/replay/diagnostics/ReplayTimelineTracing";

export interface UseReplayEngineBridgeOptions {
  readonly bridge: ReplayEngineBridge;
  readonly enabled?: boolean;
}

export function useReplayEngineBridge({
  bridge,
  enabled = true,
}: UseReplayEngineBridgeOptions): void {
  const setPlayback = useReplayTimelineStore((s) => s.setPlayback);
  const setWindow = useReplayTimelineStore((s) => s.setWindow);
  const appendMarker = useReplayTimelineStore((s) => s.appendMarker);

  useEffect(() => {
    if (!enabled) return undefined;

    // Seed initial state.
    setWindow(bridge.getSessionWindow());
    setPlayback(bridge.getPlaybackSnapshot());
    recordReplayTimelineTrace("engine-sync", "initial");

    const unsubPlayback = bridge.subscribePlayback((snapshot) => {
      setPlayback(snapshot);
      recordReplayTimelineTrace(
        "playback-state-change",
        `${snapshot.state}@${snapshot.lastSequence}`,
      );
    });

    const unsubMarkers = bridge.subscribeMarkers((marker) => {
      appendMarker(marker);
    });

    const unsubBookmarks = bridge.subscribeBookmarks((bookmarks) => {
      // Replace the in-store bookmark list — we keep them sorted
      // inside the store action.
      useReplayTimelineStore.setState((state) => ({
        bookmarks: [...bookmarks].sort((a, b) => a.sequence - b.sequence),
        stats: {
          ...state.stats,
          bookmarksAdded: state.stats.bookmarksAdded + (bookmarks.length || 0),
        },
      }));
    });

    return () => {
      unsubPlayback();
      unsubMarkers();
      unsubBookmarks();
    };
    // The bridge instance itself is the dependency — the setter
    // references from Zustand are stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bridge, enabled]);
}
