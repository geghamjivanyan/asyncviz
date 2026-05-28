import { describe, expect, it } from "vitest";
import {
  findPreset,
  makePreset,
  resolvePresets,
} from "@/dashboard/timeline/zoom/TimelineZoomPresets";

describe("zoom presets", () => {
  it("makePreset clamps degenerate bounds", () => {
    const preset = makePreset("fit-all", 5, 5);
    expect(preset.endSeconds).toBeGreaterThan(preset.startSeconds);
  });

  it("resolvePresets emits the requested presets in priority order", () => {
    const presets = resolvePresets({
      dataRange: { startSeconds: 0, endSeconds: 10 },
      selectionRange: { startSeconds: 1, endSeconds: 2 },
      activeRange: { startSeconds: 3, endSeconds: 4 },
      replayRange: { startSeconds: 5, endSeconds: 7 },
      defaultRange: { startSeconds: 0, endSeconds: 1 },
    });
    expect(presets.map((p) => p.kind)).toEqual([
      "fit-all",
      "fit-selection",
      "fit-active",
      "fit-replay",
      "fit-default",
    ]);
  });

  it("findPreset returns the matching preset", () => {
    const presets = resolvePresets({
      dataRange: { startSeconds: 0, endSeconds: 10 },
    });
    expect(findPreset(presets, "fit-all")?.kind).toBe("fit-all");
    expect(findPreset(presets, "fit-selection")).toBeNull();
  });
});
