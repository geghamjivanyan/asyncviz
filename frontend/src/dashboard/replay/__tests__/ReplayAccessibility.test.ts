import { describe, expect, it } from "vitest";

import {
  announceSeekCompleted,
  announceStateTransition,
  describeBookmarkForAccessibility,
  describeMarkerForAccessibility,
  describePlaybackForAccessibility,
  REPLAY_KEYBOARD_HELP,
} from "@/dashboard/replay/ReplayTimelineAccessibility";
import type {
  ReplayBookmark,
  ReplayPlaybackSnapshot,
  ReplaySessionWindow,
  ReplayTimelineMarker,
} from "@/dashboard/replay/models/ReplayTimelineModels";

const window: ReplaySessionWindow = {
  minSequence: 0,
  maxSequence: 200,
  minMonotonicNs: 0,
  maxMonotonicNs: 2_000_000,
};

const playback: ReplayPlaybackSnapshot = {
  state: "playing",
  speed: 2,
  lastSequence: 100,
  lastMonotonicNs: 1_000_000,
  framesDispatched: 100,
  paused: false,
};

describe("describePlaybackForAccessibility", () => {
  it("returns a humane summary", () => {
    const text = describePlaybackForAccessibility(playback, window);
    expect(text).toContain("Playing");
    expect(text).toContain("2.00x speed");
    expect(text).toContain("frame 100 of 200");
  });

  it("handles empty recordings", () => {
    const text = describePlaybackForAccessibility(playback, {
      minSequence: 0,
      maxSequence: 0,
      minMonotonicNs: 0,
      maxMonotonicNs: 0,
    });
    expect(text).toContain("no recording loaded");
  });
});

describe("describeMarkerForAccessibility", () => {
  it("includes severity, kind, frame, and percent", () => {
    const marker: ReplayTimelineMarker = {
      id: "m",
      kind: "saturation",
      severity: "critical",
      sequence: 100,
      monotonicNs: 1_000_000,
      label: "x",
      description: "Queue saturation",
    };
    const text = describeMarkerForAccessibility(marker, window);
    expect(text).toContain("Critical");
    expect(text).toContain("saturation");
    expect(text).toContain("frame 100");
    expect(text).toContain("50%");
    expect(text).toContain("Queue saturation");
  });
});

describe("describeBookmarkForAccessibility", () => {
  it("returns label + frame + percent", () => {
    const bookmark: ReplayBookmark = {
      id: "b",
      label: "First",
      sequence: 50,
      monotonicNs: 500_000,
      createdAtMs: 1,
      note: "Watch here",
    };
    const text = describeBookmarkForAccessibility(bookmark, window);
    expect(text).toContain('"First"');
    expect(text).toContain("frame 50");
    expect(text).toContain("Watch here");
  });
});

describe("announceSeekCompleted", () => {
  it("returns a percent + frame string", () => {
    expect(announceSeekCompleted(100, window)).toContain("frame 100");
    expect(announceSeekCompleted(100, window)).toContain("50%");
  });
  it("handles empty recordings", () => {
    expect(announceSeekCompleted(0, {
      minSequence: 0,
      maxSequence: 0,
      minMonotonicNs: 0,
      maxMonotonicNs: 0,
    })).toBe("Replay is empty.");
  });
});

describe("announceStateTransition", () => {
  it("returns null when nothing changed", () => {
    expect(announceStateTransition(playback, playback)).toBeNull();
  });
  it("announces state changes", () => {
    expect(announceStateTransition(playback, { ...playback, state: "paused" })).toBe(
      "Replay paused.",
    );
  });
  it("announces speed changes", () => {
    expect(announceStateTransition(playback, { ...playback, speed: 4 })).toBe(
      "Replay speed set to 4.00x.",
    );
  });
});

describe("REPLAY_KEYBOARD_HELP", () => {
  it("documents every key", () => {
    expect(REPLAY_KEYBOARD_HELP).toContain("Space");
    expect(REPLAY_KEYBOARD_HELP).toContain("Arrow");
    expect(REPLAY_KEYBOARD_HELP).toContain("Home");
    expect(REPLAY_KEYBOARD_HELP).toContain("End");
    expect(REPLAY_KEYBOARD_HELP).toContain("M");
  });
});
