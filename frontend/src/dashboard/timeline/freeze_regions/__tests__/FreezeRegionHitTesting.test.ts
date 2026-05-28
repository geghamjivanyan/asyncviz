import { describe, expect, it } from "vitest";
import {
  hitTestFreezeRegions,
  nearestFreezeRegion,
  type FreezeHitTestEntry,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionHitTesting";
import {
  makeFreezeRegionGeometry,
  makeFreezeRegionView,
} from "@/dashboard/timeline/freeze_regions/__fixtures__/makeFreezeRegionFixtures";

function entry(groupId: string, xStart: number, xEnd: number): FreezeHitTestEntry {
  return {
    region: makeFreezeRegionView({ groupId }),
    geometry: makeFreezeRegionGeometry({ groupId, xStart, xEnd }),
  };
}

describe("hitTestFreezeRegions", () => {
  it("returns null for x outside every region", () => {
    const result = hitTestFreezeRegions([entry("a", 10, 20)], 100);
    expect(result).toBeNull();
  });

  it("returns the matching region for x inside the body", () => {
    const result = hitTestFreezeRegions([entry("a", 10, 20)], 15);
    expect(result?.region.groupId).toBe("a");
  });

  it("prefers the narrowest matching region (nested freeze wins)", () => {
    const wide = entry("wide", 0, 100);
    const narrow = entry("narrow", 40, 60);
    const result = hitTestFreezeRegions([wide, narrow], 50);
    expect(result?.region.groupId).toBe("narrow");
  });
});

describe("nearestFreezeRegion", () => {
  it("returns the closest region within the tolerance", () => {
    const a = entry("a", 10, 20);
    const b = entry("b", 80, 90);
    const result = nearestFreezeRegion([a, b], 88, 5);
    expect(result?.region.groupId).toBe("b");
    expect(result?.distanceX).toBe(0);
  });

  it("returns null when nothing is within tolerance", () => {
    const a = entry("a", 10, 20);
    const result = nearestFreezeRegion([a], 100, 5);
    expect(result).toBeNull();
  });

  it("computes distance for regions to the left or right of x", () => {
    const a = entry("a", 100, 110);
    const left = nearestFreezeRegion([a], 95, 10);
    const right = nearestFreezeRegion([a], 113, 10);
    expect(left?.distanceX).toBe(5);
    expect(right?.distanceX).toBe(3);
  });
});
