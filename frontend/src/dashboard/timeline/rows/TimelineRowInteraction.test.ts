import { describe, expect, it } from "vitest";
import { hitTestRow } from "@/dashboard/timeline/rows/TimelineRowHitTesting";
import {
  resolveHover,
  resolvePrimaryClick,
} from "@/dashboard/timeline/rows/TimelineRowInteraction";
import { TimelineCoordinateSystem } from "@/dashboard/timeline/viewport/TimelineCoordinateSystem";
import { makeRowLayout } from "@/dashboard/timeline/rows/TimelineRowLayout";
import { normalizeRow } from "@/dashboard/timeline/rows/utils/normalizeRow";

function setup() {
  const coords = new TimelineCoordinateSystem(
    { timeStart: 0, timeEnd: 10, rowStart: 0, rowHeight: 22 },
    { cssWidth: 800, cssHeight: 220, devicePixelRatio: 1 },
  );
  const layout = makeRowLayout({ labelColumnWidthPx: 150, columnGutterPx: 6 }).resolve(coords);
  const rows = [normalizeRow({ rowIndex: 0, taskId: "a", label: "A" })];
  return { coords, layout, rows };
}

describe("row interaction", () => {
  it("translates a hover into a hover-row event", () => {
    const { coords, layout, rows } = setup();
    const hit = hitTestRow({ xCss: 200, yCss: 10, coords, layout, rows });
    const event = resolveHover(hit);
    expect(event.kind).toBe("hover-row");
    expect(event.taskId).toBe("a");
  });

  it("translates a label-column click into select-row", () => {
    const { coords, layout, rows } = setup();
    const hit = hitTestRow({ xCss: 40, yCss: 10, coords, layout, rows });
    const event = resolvePrimaryClick(hit);
    expect(event.kind).toBe("select-row");
    expect(event.zone).toBe("label");
  });

  it("translates a timeline-column click into select-timeline", () => {
    const { coords, layout, rows } = setup();
    const hit = hitTestRow({ xCss: 400, yCss: 10, coords, layout, rows });
    const event = resolvePrimaryClick(hit);
    expect(event.kind).toBe("select-timeline");
    expect(event.timeSeconds).not.toBeNull();
  });

  it("returns the none event when there is no row under the pointer", () => {
    const { coords, layout, rows } = setup();
    const hit = hitTestRow({ xCss: 200, yCss: 500, coords, layout, rows });
    expect(resolvePrimaryClick(hit).kind).toBe("none");
    expect(resolveHover(hit).kind).toBe("none");
  });
});
