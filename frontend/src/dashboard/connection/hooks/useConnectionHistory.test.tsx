/**
 * Tests for :func:`useConnectionHistory`.
 *
 * The hook subscribes to a :type:`ConnectionSummary` and emits ring
 * entries whenever a meaningful field changes. We drive it directly
 * to confirm the transitions.
 */

import { describe, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useConnectionHistory } from "@/dashboard/connection/hooks/useConnectionHistory";
import type { ConnectionSummary } from "@/dashboard/connection/models/state";
import { projectConnection } from "@/dashboard/connection/selectors/projectConnection";
import { INITIAL_RECONCILIATION_STATS, INITIAL_RUNTIME_META } from "@/state/runtime/models";

function summary(
  overrides: Partial<{
    phase: ConnectionSummary["phase"]["phase"];
    attempts: number;
    hydrations: number;
    lastFrameAtMonotonicMs: number;
    nowMs: number;
    windowHit: boolean;
  }> = {},
): ConnectionSummary {
  return projectConnection({
    connection: {
      phase: overrides.phase ?? "live",
      state: "open",
      reconnectAttempts: overrides.attempts ?? 0,
      lastFrameAtMonotonicMs: overrides.lastFrameAtMonotonicMs ?? 0,
    },
    runtime: {
      ...INITIAL_RUNTIME_META,
      runtimeId: "rt-1",
      status: "running",
      connectedClients: 1,
    },
    replay: {
      oldestRetainedSequence: 0,
      newestRetainedSequence: 100,
      windowHit: overrides.windowHit ?? true,
    },
    stats: {
      ...INITIAL_RECONCILIATION_STATS,
      hydrations: overrides.hydrations ?? 0,
      lastHydrationDurationMs: 10,
    },
    lastSequence: 10,
    nowMs: overrides.nowMs ?? 1000,
    hydrationInFlight: false,
  });
}

describe("useConnectionHistory", () => {
  it("seeds the ring with an initial phase entry", () => {
    const { result } = renderHook(({ s }) => useConnectionHistory(s), {
      initialProps: { s: summary() },
    });
    expect(result.current.entries.length).toBe(1);
    expect(result.current.entries[0]!.kind).toBe("phase_changed");
  });

  it("appends a phase_changed entry on phase transition", () => {
    const { result, rerender } = renderHook(({ s }) => useConnectionHistory(s), {
      initialProps: { s: summary({ phase: "live" }) },
    });
    rerender({ s: summary({ phase: "reconnecting", attempts: 1 }) });
    const kinds = result.current.entries.map((e) => e.kind);
    expect(kinds).toContain("phase_changed");
    expect(kinds).toContain("reconnect_attempted");
  });

  it("appends a hydration entry when hydrations increments", () => {
    const { result, rerender } = renderHook(({ s }) => useConnectionHistory(s), {
      initialProps: { s: summary({ hydrations: 0 }) },
    });
    rerender({ s: summary({ hydrations: 1 }) });
    expect(result.current.entries.some((e) => e.kind === "hydration_completed")).toBe(true);
  });

  it("appends a protocol_error when the replay window is missed", () => {
    const { result, rerender } = renderHook(({ s }) => useConnectionHistory(s), {
      initialProps: { s: summary({ windowHit: true }) },
    });
    rerender({ s: summary({ windowHit: false }) });
    expect(result.current.entries.some((e) => e.kind === "protocol_error")).toBe(true);
  });

  it("clear() empties the ring", () => {
    const { result, rerender } = renderHook(({ s }) => useConnectionHistory(s), {
      initialProps: { s: summary({ phase: "live" }) },
    });
    rerender({ s: summary({ phase: "reconnecting", attempts: 1 }) });
    expect(result.current.entries.length).toBeGreaterThan(0);
    act(() => result.current.clear());
    expect(result.current.entries).toHaveLength(0);
  });
});
