import { describe, expect, it } from "vitest";
import {
  DEFAULT_ZOOM_SHORTCUTS,
  hasPlatformModifier,
  matchShortcut,
} from "@/dashboard/timeline/zoom/TimelineZoomShortcuts";

describe("zoom shortcuts", () => {
  it("hasPlatformModifier accepts Ctrl + Meta", () => {
    expect(hasPlatformModifier({ key: "+", ctrlKey: true })).toBe(true);
    expect(hasPlatformModifier({ key: "+", metaKey: true })).toBe(true);
    expect(hasPlatformModifier({ key: "+" })).toBe(false);
  });

  it("matches zoom-in for Cmd/Ctrl + =", () => {
    expect(matchShortcut({ key: "=", ctrlKey: true })).toBe("zoom-in");
  });

  it("matches zoom-out for Cmd/Ctrl + -", () => {
    expect(matchShortcut({ key: "-", metaKey: true })).toBe("zoom-out");
  });

  it("matches zoom-reset for Cmd/Ctrl + 0", () => {
    expect(matchShortcut({ key: "0", ctrlKey: true })).toBe("zoom-reset");
  });

  it("matches fit-all for Cmd/Ctrl + 9", () => {
    expect(matchShortcut({ key: "9", ctrlKey: true })).toBe("fit-all");
  });

  it("returns null when no binding matches", () => {
    expect(matchShortcut({ key: "x", ctrlKey: true })).toBeNull();
    expect(matchShortcut({ key: "=" })).toBeNull(); // missing modifier
  });

  it("DEFAULT_ZOOM_SHORTCUTS exposes the documented actions", () => {
    const actions = DEFAULT_ZOOM_SHORTCUTS.map((b) => b.action);
    expect(actions).toContain("zoom-in");
    expect(actions).toContain("zoom-out");
    expect(actions).toContain("zoom-reset");
    expect(actions).toContain("fit-all");
  });
});
