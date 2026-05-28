import { describe, expect, it } from "vitest";
import { TimelineFrameBudget } from "../timeline_frame_budget";
import { default_config } from "../timeline_render_configuration";

const cfg = {
  ...default_config(),
  frameBudgetMs: 16,
  frameBudgetHardMs: 33,
  degradeAfterFrames: 3,
  restoreAfterFrames: 3,
  degradationLadder: [
    "skip-low-priority" as const,
    "coalesce-cursor" as const,
    "drop-overlays" as const,
    "keyframe-only" as const,
  ],
};

describe("TimelineFrameBudget", () => {
  it("starts at degradation step 0", () => {
    const b = new TimelineFrameBudget(cfg);
    expect(b.snapshot().degradationStep).toBe(0);
    expect(b.activeStrategies()).toHaveLength(0);
  });

  it("escalates after consecutive over-budget frames", () => {
    const b = new TimelineFrameBudget(cfg);
    for (let i = 0; i < 3; i += 1) b.recordFrame(20);
    expect(b.snapshot().degradationStep).toBe(1);
    expect(b.hasStrategy("skip-low-priority")).toBe(true);
  });

  it("does not escalate on isolated over-budget frames", () => {
    const b = new TimelineFrameBudget(cfg);
    b.recordFrame(20);
    b.recordFrame(8);
    b.recordFrame(20);
    expect(b.snapshot().degradationStep).toBe(0);
  });

  it("restores after consecutive under-budget frames", () => {
    const b = new TimelineFrameBudget(cfg);
    for (let i = 0; i < 3; i += 1) b.recordFrame(20);
    expect(b.snapshot().degradationStep).toBe(1);
    for (let i = 0; i < 3; i += 1) b.recordFrame(8);
    expect(b.snapshot().degradationStep).toBe(0);
    expect(b.snapshot().restoreTransitions).toBe(1);
  });

  it("never exceeds the ladder length", () => {
    const b = new TimelineFrameBudget(cfg);
    for (let i = 0; i < 100; i += 1) b.recordFrame(40);
    expect(b.snapshot().degradationStep).toBeLessThanOrEqual(cfg.degradationLadder.length);
  });

  it("counts frames over soft + hard budgets independently", () => {
    const b = new TimelineFrameBudget(cfg);
    b.recordFrame(8);
    b.recordFrame(20);
    b.recordFrame(40);
    const s = b.snapshot();
    expect(s.framesObserved).toBe(3);
    expect(s.framesOverSoft).toBe(2);
    expect(s.framesOverHard).toBe(1);
  });

  it("ignores non-finite durations", () => {
    const b = new TimelineFrameBudget(cfg);
    b.recordFrame(Number.NaN);
    b.recordFrame(-5);
    expect(b.snapshot().framesObserved).toBe(0);
  });

  it("reports lastOverSoft + lastOverHard", () => {
    const b = new TimelineFrameBudget(cfg);
    b.recordFrame(20);
    expect(b.lastOverSoft()).toBe(true);
    expect(b.lastOverHard()).toBe(false);
    b.recordFrame(50);
    expect(b.lastOverHard()).toBe(true);
    b.recordFrame(5);
    expect(b.lastOverSoft()).toBe(false);
  });

  it("reset returns to initial state", () => {
    const b = new TimelineFrameBudget(cfg);
    for (let i = 0; i < 10; i += 1) b.recordFrame(40);
    b.reset();
    const s = b.snapshot();
    expect(s.framesObserved).toBe(0);
    expect(s.degradationStep).toBe(0);
  });
});
