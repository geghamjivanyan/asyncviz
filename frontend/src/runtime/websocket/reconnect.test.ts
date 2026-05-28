import { describe, expect, it } from "vitest";
import { DEFAULT_MAX_DELAY_MS, ReconnectScheduler } from "@/runtime/websocket/reconnect";

describe("ReconnectScheduler", () => {
  it("returns a deterministic exponential schedule with fixed random source", () => {
    const scheduler = new ReconnectScheduler({
      baseDelayMs: 100,
      maxDelayMs: 10_000,
      jitter: 0,
      random: () => 0,
    });
    const delays = [scheduler.next(), scheduler.next(), scheduler.next(), scheduler.next()];
    expect(delays.every((d) => d !== null)).toBe(true);
    const ms = delays.map((d) => d!.delayMs);
    expect(ms).toEqual([100, 200, 400, 800]);
  });

  it("clamps delays at maxDelayMs", () => {
    const scheduler = new ReconnectScheduler({
      baseDelayMs: 1000,
      maxDelayMs: 2000,
      jitter: 0,
      random: () => 0,
    });
    const schedule = [
      scheduler.next()!.delayMs,
      scheduler.next()!.delayMs,
      scheduler.next()!.delayMs,
      scheduler.next()!.delayMs,
    ];
    expect(schedule[0]).toBe(1000);
    expect(schedule[1]).toBe(2000);
    expect(schedule[2]).toBe(2000);
    expect(schedule[3]).toBe(2000);
  });

  it("applies jitter via the random hook", () => {
    const scheduler = new ReconnectScheduler({
      baseDelayMs: 1000,
      maxDelayMs: 10_000,
      jitter: 0.2,
      random: () => 1,
    });
    // delay = base × (1 + 1 × 0.2) = 1200
    expect(scheduler.next()?.delayMs).toBe(1200);
  });

  it("caps total attempts when maxAttempts is set", () => {
    const scheduler = new ReconnectScheduler({
      baseDelayMs: 100,
      maxAttempts: 2,
      jitter: 0,
      random: () => 0,
    });
    expect(scheduler.next()).not.toBeNull();
    expect(scheduler.next()).not.toBeNull();
    expect(scheduler.next()).toBeNull();
    expect(scheduler.hasAttemptsRemaining()).toBe(false);
  });

  it("reset() clears the attempt counter", () => {
    const scheduler = new ReconnectScheduler({
      baseDelayMs: 100,
      jitter: 0,
      random: () => 0,
    });
    scheduler.next();
    scheduler.next();
    expect(scheduler.attempt).toBe(2);
    scheduler.reset();
    expect(scheduler.attempt).toBe(0);
  });

  it("default schedule respects DEFAULT_MAX_DELAY_MS", () => {
    const scheduler = new ReconnectScheduler({ jitter: 0, random: () => 0 });
    for (let i = 0; i < 20; i++) {
      const delay = scheduler.next()!.delayMs;
      expect(delay).toBeLessThanOrEqual(DEFAULT_MAX_DELAY_MS);
    }
  });
});
