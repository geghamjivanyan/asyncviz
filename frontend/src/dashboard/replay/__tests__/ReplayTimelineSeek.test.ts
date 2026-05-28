import { describe, expect, it } from "vitest";

import {
  jumpByFraction,
  seekFromFraction,
  seekFromPixel,
  seekToBookmark,
  seekToMarker,
  seekToTimestampForSequence,
  stepCursor,
} from "@/dashboard/replay/ReplayTimelineSeek";
import type {
  ReplayBookmark,
  ReplaySessionWindow,
  ReplayTimelineMarker,
  ReplayTimelineViewport,
} from "@/dashboard/replay/models/ReplayTimelineModels";

const window: ReplaySessionWindow = {
  minSequence: 0,
  maxSequence: 100,
  minMonotonicNs: 0,
  maxMonotonicNs: 1_000_000,
};

const viewport: ReplayTimelineViewport = {
  startSequence: 0,
  endSequence: 100,
  widthPx: 1000,
};

describe("seekFromPixel", () => {
  it("maps pixel to sequence intent", () => {
    expect(seekFromPixel(500, viewport)).toEqual({
      type: "seek-sequence",
      sequence: 50,
    });
  });
});

describe("seekFromFraction", () => {
  it("maps 0..1 to sequence intent", () => {
    expect(seekFromFraction(0.5, window)).toEqual({
      type: "seek-sequence",
      sequence: 50,
    });
  });
});

describe("seekToMarker / seekToBookmark", () => {
  it("uses marker sequence", () => {
    const marker: ReplayTimelineMarker = {
      id: "m",
      kind: "warning",
      severity: "info",
      sequence: 42,
      monotonicNs: 42,
      label: "x",
    };
    expect(seekToMarker(marker)).toEqual({
      type: "seek-sequence",
      sequence: 42,
    });
  });
  it("emits jump-to-bookmark for bookmarks", () => {
    const bookmark: ReplayBookmark = {
      id: "b",
      label: "x",
      sequence: 5,
      monotonicNs: 5,
      createdAtMs: 0,
    };
    expect(seekToBookmark(bookmark)).toEqual({
      type: "jump-to-bookmark",
      bookmarkId: "b",
    });
  });
});

describe("stepCursor / jumpByFraction", () => {
  it("steps respecting window bounds", () => {
    expect(stepCursor(0, -1, window)).toEqual({
      type: "seek-sequence",
      sequence: 0,
    });
    expect(stepCursor(100, 1, window)).toEqual({
      type: "seek-sequence",
      sequence: 100,
    });
    expect(stepCursor(50, 5, window)).toEqual({
      type: "seek-sequence",
      sequence: 55,
    });
  });
  it("jumps by fraction of the full window", () => {
    expect(jumpByFraction(50, 0.1, window)).toEqual({
      type: "seek-sequence",
      sequence: 60,
    });
  });
});

describe("seekToTimestampForSequence", () => {
  it("converts sequence into a timestamp intent", () => {
    expect(seekToTimestampForSequence(50, window)).toEqual({
      type: "seek-timestamp",
      monotonicNs: 500_000,
    });
  });
});
