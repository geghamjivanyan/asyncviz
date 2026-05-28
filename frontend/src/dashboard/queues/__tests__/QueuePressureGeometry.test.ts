import { describe, expect, it } from "vitest";
import {
  layoutMarker,
  layoutMarkers,
  pickMarkerAt,
} from "@/dashboard/queues/QueuePressureGeometry";
import type { QueuePressureMarker } from "@/dashboard/queues/models/QueuePressureModels";
import {
  virtualizeMarkers,
  virtualizeList,
} from "@/dashboard/queues/QueuePressureVirtualization";

const baseMarker = (overrides: Partial<QueuePressureMarker> = {}): QueuePressureMarker => ({
  id: "m-1",
  queueId: "q-1",
  kind: "pressure-change",
  severity: "warning",
  monotonicNs: 0,
  label: "calm → warning",
  ...overrides,
});

describe("layoutMarker", () => {
  it("centers the glyph at the time-mapped x", () => {
    const layout = layoutMarker(
      baseMarker({ monotonicNs: 500 }),
      { startNs: 0, endNs: 1000, viewportWidth: 200, glyphWidth: 10 },
    );
    expect(layout.x).toBeCloseTo(100, 6);
    expect(layout.left).toBeCloseTo(95, 6);
    expect(layout.clipped).toBe(false);
  });

  it("clips markers entirely outside the viewport", () => {
    const layout = layoutMarker(
      baseMarker({ monotonicNs: 2000 }),
      { startNs: 0, endNs: 1000, viewportWidth: 200 },
    );
    expect(layout.clipped).toBe(true);
  });

  it("returns a clipped layout when the window has zero span", () => {
    const layout = layoutMarker(baseMarker(), {
      startNs: 100,
      endNs: 100,
      viewportWidth: 200,
    });
    expect(layout.clipped).toBe(true);
  });
});

describe("layoutMarkers", () => {
  it("drops off-viewport markers", () => {
    const markers = [
      baseMarker({ id: "in", monotonicNs: 500 }),
      baseMarker({ id: "out", monotonicNs: 5000 }),
    ];
    const layouts = layoutMarkers(markers, {
      startNs: 0,
      endNs: 1000,
      viewportWidth: 200,
    });
    expect(layouts).toHaveLength(1);
    expect(layouts[0].marker.id).toBe("in");
  });
});

describe("pickMarkerAt", () => {
  it("returns the closest marker within tolerance", () => {
    const layouts = [
      { marker: baseMarker({ id: "a" }), x: 10, left: 5, width: 10, clipped: false },
      { marker: baseMarker({ id: "b" }), x: 50, left: 45, width: 10, clipped: false },
    ];
    const hit = pickMarkerAt(layouts, 12, 6);
    expect(hit?.marker.id).toBe("a");
  });

  it("returns null when no marker is within tolerance", () => {
    const layouts = [
      { marker: baseMarker({ id: "a" }), x: 10, left: 5, width: 10, clipped: false },
    ];
    expect(pickMarkerAt(layouts, 100, 5)).toBeNull();
  });
});

describe("virtualizeMarkers", () => {
  it("returns all markers when under the cap", () => {
    const layouts = [{ marker: baseMarker(), x: 0, left: 0, width: 10, clipped: false }];
    const out = virtualizeMarkers({ layouts, maxMarkers: 10 });
    expect(out.visible).toHaveLength(1);
    expect(out.overflow).toBe(0);
  });

  it("keeps the most recent markers when over the cap", () => {
    const layouts = Array.from({ length: 10 }, (_, i) => ({
      marker: baseMarker({ id: `m-${i}` }),
      x: i * 10,
      left: i * 10,
      width: 10,
      clipped: false,
    }));
    const out = virtualizeMarkers({ layouts, maxMarkers: 3 });
    expect(out.visible).toHaveLength(3);
    expect(out.visible[0].marker.id).toBe("m-7");
    expect(out.visible[2].marker.id).toBe("m-9");
    expect(out.overflow).toBe(7);
  });
});

describe("virtualizeList", () => {
  it("returns the visible slice + total height", () => {
    const views = Array.from({ length: 20 }, (_, i) => ({
      queueId: `q-${i}`,
    })) as unknown as Parameters<typeof virtualizeList>[0]["views"];
    const out = virtualizeList({
      views,
      viewportHeight: 100,
      rowHeight: 25,
      scrollTop: 0,
      overscan: 1,
    });
    expect(out.totalHeight).toBe(500);
    expect(out.visible.length).toBeGreaterThanOrEqual(4);
    expect(out.startIndex).toBe(0);
  });

  it("returns an empty result for an empty list", () => {
    const out = virtualizeList({
      views: [],
      viewportHeight: 100,
      rowHeight: 25,
      scrollTop: 0,
    });
    expect(out.visible).toEqual([]);
    expect(out.totalHeight).toBe(0);
  });
});
