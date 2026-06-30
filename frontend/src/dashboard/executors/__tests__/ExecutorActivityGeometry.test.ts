import { describe, expect, it } from "vitest";
import {
  layoutMarker,
  layoutMarkers,
  pickMarkerAt,
} from "@/dashboard/executors/ExecutorActivityGeometry";
import {
  virtualizeList,
  virtualizeMarkers,
} from "@/dashboard/executors/ExecutorActivityVirtualization";
import {
  hitTestMarkers,
  neighborExecutorId,
} from "@/dashboard/executors/ExecutorActivityHitTesting";
import type { ExecutorActivityMarker } from "@/dashboard/executors/models/ExecutorActivityModels";

const baseMarker = (overrides: Partial<ExecutorActivityMarker> = {}): ExecutorActivityMarker => ({
  id: "m-1",
  executorId: "e-1",
  kind: "contention",
  severity: "warning",
  monotonicNs: 0,
  label: "m",
  ...overrides,
});

describe("layoutMarker", () => {
  it("centers the glyph at the time-mapped x", () => {
    const layout = layoutMarker(baseMarker({ monotonicNs: 500 }), {
      startNs: 0,
      endNs: 1000,
      viewportWidth: 200,
      glyphWidth: 10,
    });
    expect(layout.x).toBeCloseTo(100, 6);
    expect(layout.left).toBeCloseTo(95, 6);
    expect(layout.clipped).toBe(false);
  });

  it("clips out-of-viewport markers", () => {
    const layout = layoutMarker(baseMarker({ monotonicNs: 5000 }), {
      startNs: 0,
      endNs: 1000,
      viewportWidth: 200,
    });
    expect(layout.clipped).toBe(true);
  });

  it("handles zero-span windows safely", () => {
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
    const layouts = layoutMarkers(
      [baseMarker({ id: "in", monotonicNs: 500 }), baseMarker({ id: "out", monotonicNs: 5000 })],
      { startNs: 0, endNs: 1000, viewportWidth: 200 },
    );
    expect(layouts).toHaveLength(1);
  });
});

describe("pickMarkerAt", () => {
  it("returns the closest marker within tolerance", () => {
    const layouts = [
      { marker: baseMarker({ id: "a" }), x: 10, left: 5, width: 10, clipped: false },
      { marker: baseMarker({ id: "b" }), x: 50, left: 45, width: 10, clipped: false },
    ];
    expect(pickMarkerAt(layouts, 12, 6)?.marker.id).toBe("a");
    expect(pickMarkerAt(layouts, 100, 5)).toBeNull();
  });
});

describe("virtualizeMarkers", () => {
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
    expect(out.overflow).toBe(7);
  });
});

describe("virtualizeList", () => {
  it("returns visible slice with overscan", () => {
    const views = Array.from({ length: 20 }, (_, i) => ({
      executorId: `e-${i}`,
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
  });
});

describe("hitTestMarkers", () => {
  it("returns executor id of the hit marker", () => {
    const layouts = [
      {
        marker: baseMarker({ id: "a", executorId: "e-A" }),
        x: 10,
        left: 5,
        width: 10,
        clipped: false,
      },
    ];
    const hit = hitTestMarkers(layouts, 11, 5);
    expect(hit?.executorId).toBe("e-A");
  });
});

describe("neighborExecutorId", () => {
  it("steps forward / backward through views", () => {
    const views = [
      { executorId: "a" },
      { executorId: "b" },
      { executorId: "c" },
    ] as unknown as Parameters<typeof neighborExecutorId>[0];
    expect(neighborExecutorId(views, null, 1)).toBe("a");
    expect(neighborExecutorId(views, "a", 1)).toBe("b");
    expect(neighborExecutorId(views, "c", 1)).toBe("c");
    expect(neighborExecutorId(views, "a", -1)).toBe("a");
  });
});
