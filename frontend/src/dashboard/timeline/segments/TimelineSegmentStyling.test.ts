import { describe, expect, it } from "vitest";
import { resolveSegmentStyle } from "@/dashboard/timeline/segments/TimelineSegmentStyling";
import { DEFAULT_TIMELINE_PALETTE } from "@/dashboard/timeline/rendering/TimelineColors";
import { makeProjectionEntry } from "@/dashboard/timeline/segments/__fixtures__/makeSegment";

describe("resolveSegmentStyle", () => {
  it("uses lifecycle color for the base fill", () => {
    const style = resolveSegmentStyle({
      entry: makeProjectionEntry("s", 0, 0, 1, { lifecycleState: "running" }),
      palette: DEFAULT_TIMELINE_PALETTE,
      selected: false,
    });
    expect(style.fill).toBe(DEFAULT_TIMELINE_PALETTE.success);
  });

  it("emits a hatch texture for waiting / sleeping / blocked lifecycles", () => {
    expect(
      resolveSegmentStyle({
        entry: makeProjectionEntry("s", 0, 0, 1, { lifecycleState: "waiting" }),
        palette: DEFAULT_TIMELINE_PALETTE,
        selected: false,
      }).texture,
    ).toBe("hatch");
    expect(
      resolveSegmentStyle({
        entry: makeProjectionEntry("s", 0, 0, 1, { lifecycleState: "blocked" }),
        palette: DEFAULT_TIMELINE_PALETTE,
        selected: false,
      }).texture,
    ).toBe("hatch");
  });

  it("turns on the active glow stroke for active segments", () => {
    const style = resolveSegmentStyle({
      entry: makeProjectionEntry("s", 0, 0, 1, { isActive: true, lifecycleState: "running" }),
      palette: DEFAULT_TIMELINE_PALETTE,
      selected: false,
    });
    expect(style.stroke).toBe(DEFAULT_TIMELINE_PALETTE.accent);
    expect(style.strokeWidth).toBeGreaterThan(0);
  });

  it("paints the cancelled strike for cancelled lifecycles", () => {
    const style = resolveSegmentStyle({
      entry: makeProjectionEntry("s", 0, 0, 1, { lifecycleState: "cancelled" }),
      palette: DEFAULT_TIMELINE_PALETTE,
      selected: false,
    });
    expect(style.cancelledStrike).toBe(true);
  });

  it("paints the failed border for failed lifecycles", () => {
    const style = resolveSegmentStyle({
      entry: makeProjectionEntry("s", 0, 0, 1, { lifecycleState: "failed" }),
      palette: DEFAULT_TIMELINE_PALETTE,
      selected: false,
    });
    expect(style.failedBorder).toBe(true);
  });

  it("adds a warning stroke when a warning severity is present", () => {
    const style = resolveSegmentStyle({
      entry: makeProjectionEntry("s", 0, 0, 1, {
        lifecycleState: "running",
        warningSeverity: "critical",
      }),
      palette: DEFAULT_TIMELINE_PALETTE,
      selected: false,
    });
    expect(style.warningStroke).toBe(DEFAULT_TIMELINE_PALETTE.danger);
  });

  it("emits the selection overlay only when selected", () => {
    const unselected = resolveSegmentStyle({
      entry: makeProjectionEntry("s", 0, 0, 1),
      palette: DEFAULT_TIMELINE_PALETTE,
      selected: false,
    });
    const selected = resolveSegmentStyle({
      entry: makeProjectionEntry("s", 0, 0, 1),
      palette: DEFAULT_TIMELINE_PALETTE,
      selected: true,
    });
    expect(unselected.selection).toBeNull();
    expect(selected.selection).not.toBeNull();
  });

  it("emits the replay overlay when a replay mark is attached", () => {
    const style = resolveSegmentStyle({
      entry: makeProjectionEntry("s", 0, 0, 1, {
        lifecycleState: "running",
        replay: { sequence: 1, focused: true },
      }),
      palette: DEFAULT_TIMELINE_PALETTE,
      selected: false,
    });
    expect(style.replay).not.toBeNull();
    expect(style.replay!.focused).toBe(true);
  });
});
