import { describe, expect, it } from "vitest";

import {
  pickClusterAt,
  virtualizeMarkers,
} from "@/dashboard/replay/ReplayTimelineVirtualization";
import type {
  ReplayMarkerSeverity,
  ReplayTimelineMarker,
  ReplayTimelineViewport,
} from "@/dashboard/replay/models/ReplayTimelineModels";

const viewport: ReplayTimelineViewport = {
  startSequence: 0,
  endSequence: 1000,
  widthPx: 1000,
};

const marker = (
  sequence: number,
  severity: ReplayMarkerSeverity = "info",
): ReplayTimelineMarker => ({
  id: `m-${sequence}`,
  kind: "warning",
  severity,
  sequence,
  monotonicNs: sequence,
  label: `Marker ${sequence}`,
});

describe("virtualizeMarkers", () => {
  it("returns one cluster per marker when none overlap", () => {
    const out = virtualizeMarkers([marker(0), marker(500), marker(900)], viewport);
    expect(out).toHaveLength(3);
    expect(out.every((c) => c.count === 1)).toBe(true);
  });

  it("clusters markers that fall within the cluster radius", () => {
    const out = virtualizeMarkers(
      [marker(100), marker(101), marker(102)],
      viewport,
      4,
    );
    expect(out).toHaveLength(1);
    expect(out[0].count).toBe(3);
    expect(out[0].members).toHaveLength(3);
  });

  it("escalates severity within a cluster", () => {
    const out = virtualizeMarkers(
      [marker(100, "info"), marker(101, "warning"), marker(102, "critical")],
      viewport,
      4,
    );
    expect(out[0].severity).toBe("critical");
  });

  it("excludes markers outside the viewport", () => {
    const narrow: ReplayTimelineViewport = {
      startSequence: 200,
      endSequence: 800,
      widthPx: 1000,
    };
    const out = virtualizeMarkers([marker(100), marker(500), marker(900)], narrow);
    expect(out).toHaveLength(1);
    expect(out[0].primary.sequence).toBe(500);
  });
});

describe("pickClusterAt", () => {
  it("returns the closest cluster within the radius", () => {
    const clusters = virtualizeMarkers(
      [marker(100), marker(500), marker(900)],
      viewport,
    );
    expect(pickClusterAt(clusters, 100, 5)?.primary.sequence).toBe(100);
    expect(pickClusterAt(clusters, 500, 5)?.primary.sequence).toBe(500);
    expect(pickClusterAt(clusters, 700, 5)).toBeNull();
  });
});
