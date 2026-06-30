import { describe, expect, it } from "vitest";
import {
  clampFreezeRegions,
  DEFAULT_VISIBLE_FREEZE_CAP,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionVirtualization";
import { makeFreezeRegionView } from "@/dashboard/timeline/freeze_regions/__fixtures__/makeFreezeRegionFixtures";

const buildRegions = (count: number) =>
  Array.from({ length: count }, (_, i) => makeFreezeRegionView({ groupId: `g-${i}` }));

describe("clampFreezeRegions", () => {
  it("returns the full list when under the cap", () => {
    const regions = buildRegions(5);
    const result = clampFreezeRegions(regions, 16);
    expect(result.visible.length).toBe(5);
    expect(result.hidden).toBe(0);
  });

  it("truncates and reports the hidden count", () => {
    const regions = buildRegions(10);
    const result = clampFreezeRegions(regions, 4);
    expect(result.visible.length).toBe(4);
    expect(result.hidden).toBe(6);
  });

  it("treats negative / non-finite / zero caps as 'no cap'", () => {
    const regions = buildRegions(5);
    expect(clampFreezeRegions(regions, -1).hidden).toBe(0);
    expect(clampFreezeRegions(regions, 0).hidden).toBe(0);
    expect(clampFreezeRegions(regions, Number.NaN).hidden).toBe(0);
  });

  it("defaults to DEFAULT_VISIBLE_FREEZE_CAP when omitted", () => {
    const regions = buildRegions(DEFAULT_VISIBLE_FREEZE_CAP + 4);
    const result = clampFreezeRegions(regions);
    expect(result.visible.length).toBe(DEFAULT_VISIBLE_FREEZE_CAP);
    expect(result.hidden).toBe(4);
  });
});
