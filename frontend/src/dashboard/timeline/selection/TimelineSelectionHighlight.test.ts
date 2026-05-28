import { describe, expect, it } from "vitest";
import {
  buildHighlight,
  EMPTY_HIGHLIGHT,
} from "@/dashboard/timeline/selection/TimelineSelectionHighlight";

describe("buildHighlight", () => {
  it("returns the empty highlight when nothing is selected", () => {
    expect(buildHighlight({ selectedTaskId: null })).toBe(EMPTY_HIGHLIGHT);
  });

  it("uses the selection intent by default", () => {
    const h = buildHighlight({ selectedTaskId: "t1" });
    expect(h.intent).toBe("selection");
    expect(h.pulse).toBe(false);
  });

  it("uses the warning intent when applicable", () => {
    const h = buildHighlight({ selectedTaskId: "t1", hasWarning: true });
    expect(h.intent).toBe("warning");
  });

  it("uses the replay intent + pulse when applicable", () => {
    const h = buildHighlight({ selectedTaskId: "t1", inReplay: true, hasWarning: true });
    expect(h.intent).toBe("replay");
    expect(h.pulse).toBe(true);
  });
});
