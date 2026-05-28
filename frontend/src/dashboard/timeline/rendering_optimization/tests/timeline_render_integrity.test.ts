import { describe, expect, it } from "vitest";
import { checkDirtyRegion, checkPasses, checkRedrawArea } from "../timeline_render_integrity";
import { FULL_REGION_SENTINEL, RenderPriority } from "../models";

describe("render integrity", () => {
  it("accepts the full-region sentinel", () => {
    expect(checkDirtyRegion(FULL_REGION_SENTINEL)).toBeNull();
  });

  it("flags non-finite coords", () => {
    expect(
      checkDirtyRegion({
        x: Number.NaN,
        y: 0,
        width: 1,
        height: 1,
        reason: "data",
      })?.kind,
    ).toBe("non-finite-region");
  });

  it("flags non-positive dimensions", () => {
    expect(
      checkDirtyRegion({ x: 0, y: 0, width: 0, height: 1, reason: "data" })?.kind,
    ).toBe("negative-region");
  });

  it("flags duplicate pass ids", () => {
    expect(
      checkPasses([
        {
          id: "a",
          priority: RenderPriority.NORMAL,
          regions: [],
          label: "",
          degraded: false,
        },
        {
          id: "a",
          priority: RenderPriority.NORMAL,
          regions: [],
          label: "",
          degraded: false,
        },
      ])?.kind,
    ).toBe("duplicate-pass-id");
  });

  it("flags negative priorities", () => {
    expect(
      checkPasses([
        {
          id: "a",
          priority: -1 as RenderPriority,
          regions: [],
          label: "",
          degraded: false,
        },
      ])?.kind,
    ).toBe("invalid-priority");
  });

  it("flags redraw area larger than canvas", () => {
    expect(checkRedrawArea(2_000_000, 100_000)?.kind).toBe("redraw-area-exceeds-canvas");
  });

  it("tolerates redraw area slightly over canvas (overlap)", () => {
    expect(checkRedrawArea(105_000, 100_000)).toBeNull();
  });
});
