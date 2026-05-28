import { describe, expect, it, vi } from "vitest";
import { TimelineFrameScheduler } from "@/dashboard/timeline/live/TimelineFrameScheduler";

describe("TimelineFrameScheduler", () => {
  it("forwards every requestFrame to the sink by default", () => {
    const invalidate = vi.fn();
    const scheduler = new TimelineFrameScheduler({ invalidate });
    scheduler.requestFrame("data");
    scheduler.requestFrame("camera");
    expect(invalidate).toHaveBeenCalledTimes(2);
    expect(scheduler.metrics().frameRequests).toBe(2);
  });

  it("throttles requests above maxFlushesPerSecond", () => {
    const invalidate = vi.fn();
    let now = 0;
    const scheduler = new TimelineFrameScheduler(
      { invalidate },
      { maxFlushesPerSecond: 60, now: () => now },
    );
    scheduler.requestFrame("camera");
    now += 1; // < 16.6ms interval
    scheduler.requestFrame("camera");
    expect(invalidate).toHaveBeenCalledTimes(1);
    expect(scheduler.metrics().frameRequestsSuppressed).toBe(1);
    now += 20;
    scheduler.requestFrame("camera");
    expect(invalidate).toHaveBeenCalledTimes(2);
  });
});
