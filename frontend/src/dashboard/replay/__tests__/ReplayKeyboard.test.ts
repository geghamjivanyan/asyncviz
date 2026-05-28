import { describe, expect, it } from "vitest";

import { mapKeyToIntent } from "@/dashboard/replay/hooks/useReplayKeyboard";
import type {
  ReplayPlaybackSnapshot,
  ReplaySessionWindow,
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

function keyEvent(key: string, options: Partial<KeyboardEvent> = {}): KeyboardEvent {
  // jsdom doesn't fully implement KeyboardEvent; fake the bits we
  // need for the mapper.
  return { key, shiftKey: false, ...options } as KeyboardEvent;
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

  it("ArrowRight steps one frame forward", () => {
    expect(mapKeyToIntent(keyEvent("ArrowRight"), window, playback)).toEqual({
      type: "seek-sequence",
      sequence: 51,
    });
  });

  it("Shift+ArrowRight jumps 5%", () => {
    expect(
      mapKeyToIntent(keyEvent("ArrowRight", { shiftKey: true }), window, playback),
    ).toEqual({ type: "seek-sequence", sequence: 55 });
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
