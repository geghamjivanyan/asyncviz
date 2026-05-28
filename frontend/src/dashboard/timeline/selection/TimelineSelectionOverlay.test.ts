import { describe, expect, it } from "vitest";
import { buildSelectionOverlay } from "@/dashboard/timeline/selection/TimelineSelectionOverlay";

const baseState = {
  selectedTaskId: null as string | null,
  selectedRowIndex: -1,
  selectedTask: null,
  rowCount: 5,
  atFirst: false,
  atLast: false,
  lastReason: null,
  generation: 0,
};

describe("buildSelectionOverlay", () => {
  it("returns a null payload when nothing is selected", () => {
    const overlay = buildSelectionOverlay({
      state: baseState,
      visibleStartRowIndex: 0,
      visibleEndRowIndex: 5,
      rowHeightPx: 20,
      rowStart: 0,
    });
    expect(overlay.selectedTaskId).toBeNull();
    expect(overlay.bandTopYCss).toBeNull();
    expect(overlay.insideViewport).toBe(false);
  });

  it("computes the band Y when the selection is visible", () => {
    const overlay = buildSelectionOverlay({
      state: { ...baseState, selectedTaskId: "t1", selectedRowIndex: 2 },
      visibleStartRowIndex: 0,
      visibleEndRowIndex: 5,
      rowHeightPx: 20,
      rowStart: 0,
    });
    expect(overlay.bandTopYCss).toBe(40);
    expect(overlay.bandBottomYCss).toBe(60);
    expect(overlay.insideViewport).toBe(true);
  });

  it("flags insideViewport=false when offscreen", () => {
    const overlay = buildSelectionOverlay({
      state: { ...baseState, selectedTaskId: "t1", selectedRowIndex: 10 },
      visibleStartRowIndex: 0,
      visibleEndRowIndex: 5,
      rowHeightPx: 20,
      rowStart: 0,
    });
    expect(overlay.insideViewport).toBe(false);
  });
});
