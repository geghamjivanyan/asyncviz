import { describe, expect, it } from "vitest";
import {
  describeFreezeCountsAnnouncement,
  describeFreezeFocusAnnouncement,
  describeFreezeForAccessibility,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionAccessibility";
import { makeFreezeRegionView } from "@/dashboard/timeline/freeze_regions/__fixtures__/makeFreezeRegionFixtures";

describe("describeFreezeForAccessibility", () => {
  it("includes intent, window, duration, captures, and task", () => {
    const region = makeFreezeRegionView();
    const label = describeFreezeForAccessibility(region);
    expect(label).toMatch(/critical freeze/);
    expect(label).toMatch(/window win-1/);
    expect(label).toMatch(/duration/);
    expect(label).toMatch(/3 correlated captures/);
    expect(label).toMatch(/task render-loop/);
  });

  it("mentions peak severity only when it differs from the current severity", () => {
    const same = describeFreezeForAccessibility(makeFreezeRegionView());
    expect(same).not.toMatch(/peak severity/);
    const escalated = describeFreezeForAccessibility(
      makeFreezeRegionView({ severity: "WARNING", peakSeverity: "FREEZE" }),
    );
    expect(escalated).toMatch(/peak severity FREEZE/);
  });

  it("formats sub-second durations in ms", () => {
    const region = makeFreezeRegionView({
      startSeconds: 0,
      endSeconds: 0.25,
    });
    const label = describeFreezeForAccessibility({ ...region, durationSeconds: 0.25 });
    expect(label).toMatch(/duration 250 ms/);
  });
});

describe("describeFreezeCountsAnnouncement", () => {
  it("handles empty state", () => {
    expect(describeFreezeCountsAnnouncement(0, 0, 0)).toMatch(/No freeze regions/);
  });

  it("singular active / plural variants", () => {
    expect(describeFreezeCountsAnnouncement(1, 0, 1)).toMatch(/1 active freeze region/);
    expect(describeFreezeCountsAnnouncement(2, 0, 2)).toMatch(/2 active freeze regions/);
  });

  it("includes recovered + visible counts when present", () => {
    const s = describeFreezeCountsAnnouncement(2, 3, 4);
    expect(s).toMatch(/2 active freeze regions/);
    expect(s).toMatch(/3 recovered/);
    expect(s).toMatch(/4 currently visible/);
  });
});

describe("describeFreezeFocusAnnouncement", () => {
  it("names the freeze + duration", () => {
    const region = makeFreezeRegionView();
    expect(describeFreezeFocusAnnouncement(region)).toMatch(
      /Focused critical freeze win-1, duration/,
    );
  });

  it("falls back to 'no-window' when there's no window id", () => {
    const region = makeFreezeRegionView({ windowId: null });
    expect(describeFreezeFocusAnnouncement(region)).toMatch(/no-window/);
  });
});
