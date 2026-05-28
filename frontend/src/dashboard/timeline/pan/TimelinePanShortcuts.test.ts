import { describe, expect, it } from "vitest";
import {
  DEFAULT_PAN_SHORTCUTS,
  matchPanShortcut,
} from "@/dashboard/timeline/pan/TimelinePanShortcuts";

describe("pan shortcuts", () => {
  it("matches ArrowLeft / ArrowRight", () => {
    expect(matchPanShortcut({ key: "ArrowLeft" })).toBe("pan-left");
    expect(matchPanShortcut({ key: "ArrowRight" })).toBe("pan-right");
  });

  it("matches shift variants", () => {
    expect(matchPanShortcut({ key: "ArrowLeft", shiftKey: true })).toBe("pan-left-fast");
    expect(matchPanShortcut({ key: "ArrowRight", shiftKey: true })).toBe("pan-right-fast");
  });

  it("matches Home / End", () => {
    expect(matchPanShortcut({ key: "Home" })).toBe("pan-home");
    expect(matchPanShortcut({ key: "End" })).toBe("pan-end");
  });

  it("returns null when no binding matches", () => {
    expect(matchPanShortcut({ key: "x" })).toBeNull();
    expect(matchPanShortcut({ key: "ArrowLeft", ctrlKey: true })).toBeNull();
  });

  it("DEFAULT_PAN_SHORTCUTS exposes the documented actions", () => {
    const actions = DEFAULT_PAN_SHORTCUTS.map((b) => b.action);
    expect(actions).toContain("pan-left");
    expect(actions).toContain("pan-right");
    expect(actions).toContain("pan-home");
    expect(actions).toContain("pan-end");
  });
});
