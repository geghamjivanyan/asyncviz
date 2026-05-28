import { describe, expect, it } from "vitest";

import {
  bucketMarkers,
  findNearestMarker,
  projectBookmarks,
  projectMarkers,
} from "@/dashboard/replay/ReplayTimelineProjection";
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

const marker = (
  sequence: number,
  severity: ReplayTimelineMarker["severity"] = "info",
): ReplayTimelineMarker => ({
  id: `m-${sequence}`,
  kind: "warning",
  severity,
  sequence,
  monotonicNs: sequence * 10,
  label: `Marker ${sequence}`,
});

describe("projectMarkers", () => {
  it("returns pixel placements for in-viewport markers", () => {
    const out = projectMarkers([marker(10), marker(50), marker(90)], viewport);
    expect(out).toHaveLength(3);
    expect(out[0].pixelX).toBe(100);
    expect(out[1].pixelX).toBe(500);
    expect(out[2].pixelX).toBe(900);
  });
  it("skips off-viewport markers", () => {
    const out = projectMarkers([marker(-5), marker(150)], viewport);
    expect(out).toHaveLength(0);
  });
  it("returns empty for zero-width viewports", () => {
    const out = projectMarkers([marker(50)], { ...viewport, widthPx: 0 });
    expect(out).toHaveLength(0);
  });
});

describe("projectBookmarks", () => {
  it("places bookmarks like markers", () => {
    const bookmark: ReplayBookmark = {
      id: "b-1",
      label: "First",
      sequence: 25,
      monotonicNs: 250,
      createdAtMs: 1,
    };
    const out = projectBookmarks([bookmark], viewport);
    expect(out[0].pixelX).toBe(250);
  });
});

describe("bucketMarkers", () => {
  it("places markers in the right buckets", () => {
    const markers = [marker(5), marker(55), marker(95, "critical")];
    const buckets = bucketMarkers(markers, window, 10);
    expect(buckets).toHaveLength(10);
    const total = buckets.reduce((sum, b) => sum + b.markerCount, 0);
    expect(total).toBe(3);
    const critical = buckets.reduce(
      (sum, b) => sum + b.severityCount.critical,
      0,
    );
    expect(critical).toBe(1);
  });
  it("returns empty for zero bucketCount or empty window", () => {
    expect(bucketMarkers([marker(1)], window, 0)).toEqual([]);
    expect(
      bucketMarkers([marker(1)], { ...window, maxSequence: 0 }, 4),
    ).toEqual([]);
  });
});

describe("findNearestMarker", () => {
  it("returns the closest marker", () => {
    const markers = [marker(0), marker(50), marker(100)];
    expect(findNearestMarker(markers, 49)?.sequence).toBe(50);
    expect(findNearestMarker(markers, 1)?.sequence).toBe(0);
  });
  it("returns null for empty input", () => {
    expect(findNearestMarker([], 5)).toBeNull();
  });
});
