import { describe, expect, it } from "vitest";

import {
  initialReplayTimelineState,
  reduceAddBookmark,
  reduceAppendMarker,
  reduceBeginScrub,
  reduceEndScrub,
  reducePlayback,
  reduceRemoveBookmark,
  reduceUpdateScrub,
} from "@/dashboard/replay/ReplayTimelineStore";
import type {
  ReplayPlaybackSnapshot,
  ReplayScrubPreview,
  ReplayTimelineMarker,
} from "@/dashboard/replay/models/ReplayTimelineModels";

const snapshot = (overrides: Partial<ReplayPlaybackSnapshot> = {}): ReplayPlaybackSnapshot => ({
  state: "playing",
  speed: 1,
  lastSequence: 10,
  lastMonotonicNs: 1000,
  framesDispatched: 10,
  paused: false,
  ...overrides,
});

const marker = (sequence: number): ReplayTimelineMarker => ({
  id: `m-${sequence}`,
  kind: "warning",
  severity: "info",
  sequence,
  monotonicNs: sequence,
  label: `m${sequence}`,
});

describe("reducePlayback", () => {
  it("swaps playback + bumps stats", () => {
    const state = initialReplayTimelineState();
    const out = reducePlayback(state, snapshot());
    expect(out.playback?.lastSequence).toBe(10);
    expect(out.stats?.playbackUpdatesApplied).toBe(1);
  });
});

describe("reduceAppendMarker", () => {
  it("keeps markers sorted by sequence", () => {
    let state = initialReplayTimelineState();
    state = { ...state, ...reduceAppendMarker(state, marker(50)) };
    state = { ...state, ...reduceAppendMarker(state, marker(10)) };
    state = { ...state, ...reduceAppendMarker(state, marker(30)) };
    expect(state.markers.map((m) => m.sequence)).toEqual([10, 30, 50]);
  });
});

describe("reduceAddBookmark / reduceRemoveBookmark", () => {
  it("dedupes by id + sorts by sequence", () => {
    let state = initialReplayTimelineState();
    state = {
      ...state,
      ...reduceAddBookmark(state, {
        id: "b1",
        label: "a",
        sequence: 50,
        monotonicNs: 50,
        createdAtMs: 1,
      }),
    };
    state = {
      ...state,
      ...reduceAddBookmark(state, {
        id: "b1",
        label: "renamed",
        sequence: 10,
        monotonicNs: 10,
        createdAtMs: 2,
      }),
    };
    expect(state.bookmarks).toHaveLength(1);
    expect(state.bookmarks[0].label).toBe("renamed");
    state = { ...state, ...reduceRemoveBookmark(state, "b1") };
    expect(state.bookmarks).toHaveLength(0);
  });
});

describe("scrub reducers", () => {
  const preview: ReplayScrubPreview = {
    sequence: 5,
    monotonicNs: 5,
    clientX: 0,
    normalizedFraction: 0,
  };

  it("transitions through begin → update → end", () => {
    let state = initialReplayTimelineState();
    state = { ...state, ...reduceBeginScrub(state, preview) };
    expect(state.scrubPhase).toBe("dragging");
    state = {
      ...state,
      ...reduceUpdateScrub(state, { ...preview, sequence: 10 }),
    };
    expect(state.scrubPreview?.sequence).toBe(10);
    state = { ...state, ...reduceEndScrub(state) };
    expect(state.scrubPhase).toBe("idle");
    expect(state.scrubPreview).toBeNull();
  });

  it("ignores updates when not dragging", () => {
    const state = initialReplayTimelineState();
    const out = reduceUpdateScrub(state, preview);
    expect(out.scrubPreview).toBeUndefined();
  });
});
