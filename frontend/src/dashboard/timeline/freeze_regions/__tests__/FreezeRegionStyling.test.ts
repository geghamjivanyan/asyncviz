import { describe, expect, it } from "vitest";
import { resolveBodyStyle } from "@/dashboard/timeline/freeze_regions/FreezeRegionStyling";
import { DEFAULT_FREEZE_REGION_PALETTE } from "@/dashboard/timeline/freeze_regions/FreezeRegionColors";
import { makeFreezeRegionView } from "@/dashboard/timeline/freeze_regions/__fixtures__/makeFreezeRegionFixtures";

const PALETTE = DEFAULT_FREEZE_REGION_PALETTE;

describe("resolveBodyStyle", () => {
  it("uses active fill for active lifecycle", () => {
    const region = makeFreezeRegionView({ lifecycle: "active", intent: "freeze" });
    const style = resolveBodyStyle(region, PALETTE, null, null);
    expect(style.fill).toBe(PALETTE.activeFill.freeze);
    expect(style.border).toBe(PALETTE.border.freeze);
  });

  it("uses recovered fill for recovered lifecycle", () => {
    const region = makeFreezeRegionView({
      lifecycle: "recovered",
      state: "recovered",
      intent: "resolved",
    });
    const style = resolveBodyStyle(region, PALETTE, null, null);
    expect(style.fill).toBe(PALETTE.recoveredFill.resolved);
  });

  it("flags active+active state as pulsing", () => {
    const region = makeFreezeRegionView({ lifecycle: "active", state: "active" });
    expect(resolveBodyStyle(region, PALETTE, null, null).pulse).toBe(true);
  });

  it("does not pulse for opened/escalating active regions", () => {
    expect(
      resolveBodyStyle(
        makeFreezeRegionView({ lifecycle: "active", state: "opened" }),
        PALETTE,
        null,
        null,
      ).pulse,
    ).toBe(false);
  });

  it("uses selection palette when the region is selected", () => {
    const region = makeFreezeRegionView({ groupId: "sel" });
    const style = resolveBodyStyle(region, PALETTE, "sel", null);
    expect(style.fill).toBe(PALETTE.selectionFill);
    expect(style.border).toBe(PALETTE.selectionStroke);
  });

  it("uses hover stroke when hovered (but not selected)", () => {
    const region = makeFreezeRegionView({ groupId: "h" });
    const style = resolveBodyStyle(region, PALETTE, null, "h");
    expect(style.border).toBe(PALETTE.hoverStroke);
  });
});
