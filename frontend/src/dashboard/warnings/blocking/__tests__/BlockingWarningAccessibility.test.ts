import { describe, expect, it } from "vitest";
import {
  describeCountsAnnouncement,
  describeTransitionAnnouncement,
  describeViewForAccessibility,
} from "@/dashboard/warnings/blocking/BlockingWarningAccessibility";
import { projectGroup } from "@/dashboard/warnings/blocking/selectors/BlockingWarningSelectors";
import { makeGroup } from "@/dashboard/warnings/blocking/__fixtures__/makeBlockingWarningFixtures";

describe("BlockingWarningAccessibility", () => {
  it("includes severity, state, duration, lag, captures, and task", () => {
    const view = projectGroup(makeGroup());
    const label = describeViewForAccessibility(view);
    expect(label).toMatch(/critical active blocking warning/i);
    expect(label).toMatch(/window win-1/);
    expect(label).toMatch(/duration/);
    expect(label).toMatch(/peak lag/);
    expect(label).toMatch(/3 correlated captures/);
    expect(label).toMatch(/task render-loop/);
  });

  it("describes empty state as 'no warnings'", () => {
    expect(describeCountsAnnouncement(0, 0, false)).toMatch(/No blocking warnings/);
  });

  it("describes filtered empty state", () => {
    expect(describeCountsAnnouncement(0, 0, true)).toMatch(/match the current filter/);
  });

  it("describes counts with proper pluralization", () => {
    expect(describeCountsAnnouncement(1, 0, false)).toMatch(/1 active blocking warning,/);
    expect(describeCountsAnnouncement(3, 2, true)).toMatch(/3 active blocking warnings, 2 recent, filtered view/);
  });

  it("transition announcement embeds state + severity + window", () => {
    const view = projectGroup(makeGroup({ state: "active", severity: "FREEZE" }));
    expect(describeTransitionAnnouncement(view)).toMatch(/Blocking active \(freeze\) on window win-1/);
  });
});
