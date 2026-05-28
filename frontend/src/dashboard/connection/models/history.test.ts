import { describe, expect, it } from "vitest";
import { appendHistory, clearHistory } from "@/dashboard/connection/models/history";
import { HISTORY_RING_CAPACITY } from "@/dashboard/connection/models/state";

describe("appendHistory", () => {
  it("appends an entry to the end", () => {
    const next = appendHistory([], {
      kind: "phase_changed",
      phase: "live",
      sequence: 1,
      reconnectAttempts: 0,
      detail: "x",
      atMonotonicMs: 100,
      atWallMs: 200,
    });
    expect(next).toHaveLength(1);
    expect(next[0]).toMatchObject({
      kind: "phase_changed",
      phase: "live",
      sequence: 1,
      reconnectAttempts: 0,
      detail: "x",
      atMonotonicMs: 100,
      atWallMs: 200,
    });
  });

  it("evicts the oldest entry when over capacity", () => {
    let history: ReturnType<typeof appendHistory> = [];
    for (let i = 0; i < HISTORY_RING_CAPACITY + 5; i += 1) {
      history = appendHistory(history, {
        kind: "phase_changed",
        phase: "live",
        sequence: i,
        reconnectAttempts: 0,
        detail: `step-${i}`,
        atMonotonicMs: i,
        atWallMs: i,
      });
    }
    expect(history.length).toBe(HISTORY_RING_CAPACITY);
    expect(history[0]!.detail).toBe("step-5");
  });

  it("respects a custom capacity", () => {
    const history = [1, 2, 3, 4]
      .map((i) => ({ atMonotonicMs: i }))
      .reduce(
        (acc, sample) =>
          appendHistory(acc, {
            kind: "phase_changed",
            phase: "live",
            sequence: 1,
            reconnectAttempts: 0,
            detail: "x",
            atMonotonicMs: sample.atMonotonicMs,
            capacity: 2,
          }),
        [] as ReturnType<typeof appendHistory>,
      );
    expect(history).toHaveLength(2);
    expect(history[0]!.atMonotonicMs).toBe(3);
  });
});

describe("clearHistory", () => {
  it("returns an empty array", () => {
    expect(clearHistory()).toHaveLength(0);
  });
});
