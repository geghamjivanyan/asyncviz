import { afterEach, describe, expect, it, vi } from "vitest";

import { InMemoryReplayEngineBridge } from "@/dashboard/replay/hooks/ReplayEngineBridge";
import type {
  ReplayBookmark,
  ReplayTimelineMarker,
} from "@/dashboard/replay/models/ReplayTimelineModels";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("InMemoryReplayEngineBridge", () => {
  it("fans playback updates to subscribers", () => {
    const bridge = new InMemoryReplayEngineBridge();
    const listener = vi.fn();
    const unsubscribe = bridge.subscribePlayback(listener);
    bridge.setPlayback({
      state: "playing",
      speed: 1,
      lastSequence: 5,
      lastMonotonicNs: 5,
      framesDispatched: 5,
      paused: false,
    });
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
    bridge.setPlayback({
      state: "paused",
      speed: 1,
      lastSequence: 5,
      lastMonotonicNs: 5,
      framesDispatched: 5,
      paused: true,
    });
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("fans markers to subscribers", () => {
    const bridge = new InMemoryReplayEngineBridge();
    const received: ReplayTimelineMarker[] = [];
    bridge.subscribeMarkers((m) => received.push(m));
    bridge.emitMarker({
      id: "m1",
      kind: "warning",
      severity: "info",
      sequence: 10,
      monotonicNs: 100,
      label: "x",
    });
    expect(received).toHaveLength(1);
  });

  it("fans bookmarks as snapshots", () => {
    const bridge = new InMemoryReplayEngineBridge();
    const received: readonly ReplayBookmark[][] = [];
    bridge.subscribeBookmarks((bookmarks) => {
      (received as ReplayBookmark[][]).push([...bookmarks]);
    });
    bridge.setBookmarks([{ id: "b1", label: "x", sequence: 5, monotonicNs: 5, createdAtMs: 1 }]);
    expect(received[0]).toHaveLength(1);
  });

  it("records dispatched intents", () => {
    const bridge = new InMemoryReplayEngineBridge();
    bridge.dispatch({ type: "play" });
    bridge.dispatch({ type: "seek-sequence", sequence: 10 });
    expect(bridge.intents).toEqual([{ type: "play" }, { type: "seek-sequence", sequence: 10 }]);
  });
});
