import { beforeEach, describe, expect, it } from "vitest";
import { useFreezeRegionStore } from "@/dashboard/timeline/freeze_regions/FreezeRegionStore";
import {
  makeFreezeRegionGeometry,
  makeFreezeRegionView,
} from "@/dashboard/timeline/freeze_regions/__fixtures__/makeFreezeRegionFixtures";

beforeEach(() => {
  useFreezeRegionStore.getState().reset();
});

describe("useFreezeRegionStore", () => {
  it("starts with sane defaults", () => {
    const state = useFreezeRegionStore.getState();
    expect(state.selectedGroupId).toBeNull();
    expect(state.hoveredGroupId).toBeNull();
    expect(state.visibleEntries).toEqual([]);
    expect(state.hiddenCount).toBe(0);
    expect(state.revealedGroupId).toBeNull();
    expect(state.reducedMotion).toBe(false);
  });

  it("setSelectedGroup keeps the slice stable on repeated identical writes", () => {
    useFreezeRegionStore.getState().setSelectedGroup("a");
    useFreezeRegionStore.getState().setSelectedGroup("a");
    expect(useFreezeRegionStore.getState().selectedGroupId).toBe("a");
    useFreezeRegionStore.getState().setSelectedGroup("b");
    expect(useFreezeRegionStore.getState().selectedGroupId).toBe("b");
  });

  it("setHoveredGroup keeps the slice stable on repeated identical writes", () => {
    useFreezeRegionStore.getState().setHoveredGroup("a");
    useFreezeRegionStore.getState().setHoveredGroup("a");
    expect(useFreezeRegionStore.getState().hoveredGroupId).toBe("a");
    useFreezeRegionStore.getState().setHoveredGroup(null);
    expect(useFreezeRegionStore.getState().hoveredGroupId).toBeNull();
  });

  it("setVisibleEntries stores entries + hidden count", () => {
    const entries = [
      {
        region: makeFreezeRegionView({ groupId: "a" }),
        geometry: makeFreezeRegionGeometry({ groupId: "a" }),
      },
    ];
    useFreezeRegionStore.getState().setVisibleEntries(entries, 3);
    expect(useFreezeRegionStore.getState().visibleEntries).toBe(entries);
    expect(useFreezeRegionStore.getState().hiddenCount).toBe(3);
  });

  it("revealGroup updates the revealed slot", () => {
    useFreezeRegionStore.getState().revealGroup("xyz");
    expect(useFreezeRegionStore.getState().revealedGroupId).toBe("xyz");
    useFreezeRegionStore.getState().revealGroup(null);
    expect(useFreezeRegionStore.getState().revealedGroupId).toBeNull();
  });

  it("reset returns to initial state", () => {
    useFreezeRegionStore.getState().setSelectedGroup("a");
    useFreezeRegionStore.getState().setHoveredGroup("b");
    useFreezeRegionStore.getState().revealGroup("c");
    useFreezeRegionStore.getState().setReducedMotion(true);
    useFreezeRegionStore.getState().reset();
    const state = useFreezeRegionStore.getState();
    expect(state.selectedGroupId).toBeNull();
    expect(state.hoveredGroupId).toBeNull();
    expect(state.revealedGroupId).toBeNull();
    expect(state.reducedMotion).toBe(false);
  });
});
