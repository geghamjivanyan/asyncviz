import { describe, expect, it } from "vitest";
import { clampViews } from "@/dashboard/warnings/blocking/BlockingWarningVirtualization";
import { projectGroup } from "@/dashboard/warnings/blocking/selectors/BlockingWarningSelectors";
import { makeGroup } from "@/dashboard/warnings/blocking/__fixtures__/makeBlockingWarningFixtures";

const buildViews = (count: number) =>
  Array.from({ length: count }, (_, i) =>
    projectGroup(makeGroup({ group_id: `g-${i}` })),
  );

describe("clampViews", () => {
  it("returns full list when under the cap", () => {
    const views = buildViews(3);
    const result = clampViews(views, 8);
    expect(result.visible.length).toBe(3);
    expect(result.hidden).toBe(0);
  });

  it("truncates and reports the hidden count", () => {
    const views = buildViews(10);
    const result = clampViews(views, 4);
    expect(result.visible.length).toBe(4);
    expect(result.hidden).toBe(6);
  });

  it("treats negative or non-finite caps as 'no cap'", () => {
    const views = buildViews(5);
    expect(clampViews(views, -1).hidden).toBe(0);
    expect(clampViews(views, Number.NaN).hidden).toBe(0);
  });
});
