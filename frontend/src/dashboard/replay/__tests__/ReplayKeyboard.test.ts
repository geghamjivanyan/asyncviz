import { describe, expect, it } from "vitest";

import { mapKeyToIntent } from "@/dashboard/replay/hooks/useReplayKeyboard";
import type {
  ReplayBookmark,
  ReplayPlaybackSnapshot,
  ReplaySessionWindow,
  ReplayTimelineMarker,
} from "@/dashboard/replay/models/ReplayTimelineModels";

const window: ReplaySessionWindow = {
  minSequence: 0,
  maxSequence: 100,
  minMonotonicNs: 0,
  maxMonotonicNs: 1_000_000,
};

const playback: ReplayPlaybackSnapshot = {
  state: "playing",
  speed: 1,
  lastSequence: 50,
  lastMonotonicNs: 500_000,
  framesDispatched: 50,
  paused: false,
};

const markers: ReplayTimelineMarker[] = [
  {
    id: "m-30",
    kind: "warning",
    severity: "warning",
    sequence: 30,
    monotonicNs: 300_000,
    label: "earlier",
  },
  {
    id: "m-70",
    kind: "blocking",
    severity: "critical",
    sequence: 70,
    monotonicNs: 700_000,
    label: "later",
  },
];

const bookmarks: ReplayBookmark[] = [
  {
    id: "bm-20",
    label: "first",
    sequence: 20,
    monotonicNs: 200_000,
    createdAtMs: 0,
  },
  {
    id: "bm-80",
    label: "last",
    sequence: 80,
    monotonicNs: 800_000,
    createdAtMs: 0,
  },
];

function keyEvent(key: string, options: Partial<KeyboardEvent> = {}): KeyboardEvent {
  // jsdom doesn't fully implement KeyboardEvent; fake the bits we
  // need for the mapper.
  return {
    key,
    shiftKey: false,
    ctrlKey: false,
    metaKey: false,
    ...options,
  } as KeyboardEvent;
}

describe("mapKeyToIntent", () => {
  it("space toggles pause", () => {
    expect(mapKeyToIntent(keyEvent(" "), window, playback)).toEqual({
      type: "pause",
    });
    expect(
      mapKeyToIntent(keyEvent(" "), window, { ...playback, paused: true }),
    ).toEqual({ type: "play" });
  });

  it("ArrowRight steps one event forward", () => {
    expect(mapKeyToIntent(keyEvent("ArrowRight"), window, playback)).toEqual({
      type: "seek-sequence",
      sequence: 51,
    });
  });

  it("ArrowLeft steps one event backward", () => {
    expect(mapKeyToIntent(keyEvent("ArrowLeft"), window, playback)).toEqual({
      type: "seek-sequence",
      sequence: 49,
    });
  });

  it("Shift+ArrowRight jumps to the next marker", () => {
    expect(
      mapKeyToIntent(
        keyEvent("ArrowRight", { shiftKey: true }),
        window,
        playback,
        { markers },
      ),
    ).toEqual({ type: "seek-sequence", sequence: 70 });
  });

  it("Shift+ArrowLeft jumps to the previous marker", () => {
    expect(
      mapKeyToIntent(
        keyEvent("ArrowLeft", { shiftKey: true }),
        window,
        playback,
        { markers },
      ),
    ).toEqual({ type: "seek-sequence", sequence: 30 });
  });

  it("Shift+ArrowRight is a no-op when no later marker exists", () => {
    expect(
      mapKeyToIntent(
        keyEvent("ArrowRight", { shiftKey: true }),
        window,
        { ...playback, lastSequence: 80 },
        { markers },
      ),
    ).toBeNull();
  });

  it("Ctrl+ArrowRight jumps to the next bookmark", () => {
    expect(
      mapKeyToIntent(
        keyEvent("ArrowRight", { ctrlKey: true }),
        window,
        playback,
        { bookmarks },
      ),
    ).toEqual({ type: "jump-to-bookmark", bookmarkId: "bm-80" });
  });

  it("Cmd+ArrowLeft jumps to the previous bookmark", () => {
    expect(
      mapKeyToIntent(
        keyEvent("ArrowLeft", { metaKey: true }),
        window,
        playback,
        { bookmarks },
      ),
    ).toEqual({ type: "jump-to-bookmark", bookmarkId: "bm-20" });
  });

  it("Home + End jump to bounds", () => {
    expect(mapKeyToIntent(keyEvent("Home"), window, playback)).toEqual({
      type: "seek-sequence",
      sequence: 0,
    });
    expect(mapKeyToIntent(keyEvent("End"), window, playback)).toEqual({
      type: "seek-sequence",
      sequence: 100,
    });
  });

  it("PageDown jumps 10% forward", () => {
    expect(mapKeyToIntent(keyEvent("PageDown"), window, playback)).toEqual({
      type: "seek-sequence",
      sequence: 60,
    });
  });

  it("Period steps forward via step-forward", () => {
    expect(mapKeyToIntent(keyEvent("."), window, playback)).toEqual({
      type: "step-forward",
    });
  });

  it("m signals bookmark", () => {
    expect(mapKeyToIntent(keyEvent("m"), window, playback)).toBe("bookmark");
  });

  it("unknown keys produce null", () => {
    expect(mapKeyToIntent(keyEvent("F1"), window, playback)).toBeNull();
  });
});
