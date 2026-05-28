import { describe, expect, it } from "vitest";
import {
  centerWindowOnSelection,
  minimalRevealDelta,
  selectionAtLeastPartiallyVisible,
  selectionFullyVisible,
} from "@/dashboard/timeline/selection/TimelineSelectionFocus";

const selection = { startSeconds: 5, endSeconds: 7 };

describe("selection focus", () => {
  it("selectionFullyVisible detects an enclosed selection", () => {
    expect(selectionFullyVisible(selection, { startSeconds: 0, endSeconds: 10 })).toBe(true);
    expect(selectionFullyVisible(selection, { startSeconds: 0, endSeconds: 6 })).toBe(false);
  });

  it("selectionAtLeastPartiallyVisible detects any overlap", () => {
    expect(
      selectionAtLeastPartiallyVisible(selection, { startSeconds: 0, endSeconds: 6 }),
    ).toBe(true);
    expect(
      selectionAtLeastPartiallyVisible(selection, { startSeconds: 10, endSeconds: 20 }),
    ).toBe(false);
  });

  it("centerWindowOnSelection centers the supplied duration", () => {
    expect(centerWindowOnSelection(selection, 4)).toBe(4);
  });

  it("minimalRevealDelta is zero when the selection is visible", () => {
    expect(minimalRevealDelta(selection, { startSeconds: 0, endSeconds: 10 })).toBe(0);
  });

  it("minimalRevealDelta pans left when the selection is to the left", () => {
    expect(minimalRevealDelta(selection, { startSeconds: 8, endSeconds: 18 })).toBeLessThan(0);
  });

  it("minimalRevealDelta pans right when the selection is to the right", () => {
    expect(minimalRevealDelta(selection, { startSeconds: 0, endSeconds: 6 })).toBeGreaterThan(0);
  });
});
