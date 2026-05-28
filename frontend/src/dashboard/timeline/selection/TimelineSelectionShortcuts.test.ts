import { describe, expect, it } from "vitest";
import {
  DEFAULT_SELECTION_SHORTCUTS,
  matchSelectionShortcut,
} from "@/dashboard/timeline/selection/TimelineSelectionShortcuts";

describe("selection shortcuts", () => {
  it("matches ArrowUp / ArrowDown", () => {
    expect(matchSelectionShortcut({ key: "ArrowDown" })).toBe("select-next");
    expect(matchSelectionShortcut({ key: "ArrowUp" })).toBe("select-previous");
  });

  it("matches Shift+Home and Shift+End", () => {
    expect(matchSelectionShortcut({ key: "Home", shiftKey: true })).toBe("select-first");
    expect(matchSelectionShortcut({ key: "End", shiftKey: true })).toBe("select-last");
  });

  it("matches Escape / F / R", () => {
    expect(matchSelectionShortcut({ key: "Escape" })).toBe("clear-selection");
    expect(matchSelectionShortcut({ key: "F" })).toBe("center-selection");
    expect(matchSelectionShortcut({ key: "r" })).toBe("reveal-selection");
  });

  it("returns null for unknown keys", () => {
    expect(matchSelectionShortcut({ key: "Tab" })).toBeNull();
    expect(matchSelectionShortcut({ key: "ArrowDown", ctrlKey: true })).toBeNull();
  });

  it("DEFAULT_SELECTION_SHORTCUTS exposes the documented actions", () => {
    const actions = DEFAULT_SELECTION_SHORTCUTS.map((b) => b.action);
    expect(actions).toContain("select-next");
    expect(actions).toContain("select-previous");
    expect(actions).toContain("clear-selection");
    expect(actions).toContain("center-selection");
    expect(actions).toContain("reveal-selection");
  });
});
