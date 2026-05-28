import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { ConnectionTooltip } from "@/dashboard/connection/components/ConnectionTooltip";
import { projectConnection } from "@/dashboard/connection/selectors/projectConnection";
import { INITIAL_RECONCILIATION_STATS, INITIAL_RUNTIME_META } from "@/state/runtime/models";

function syntheticSummary() {
  return projectConnection({
    connection: {
      phase: "live",
      state: "open",
      reconnectAttempts: 0,
      lastFrameAtMonotonicMs: 0,
    },
    runtime: {
      ...INITIAL_RUNTIME_META,
      runtimeId: "rt-1",
      status: "running",
      connectedClients: 5,
    },
    replay: {
      oldestRetainedSequence: 0,
      newestRetainedSequence: 100,
      windowHit: true,
    },
    stats: {
      ...INITIAL_RECONCILIATION_STATS,
      hydrations: 1,
      lastHydrationDurationMs: 42,
    },
    lastSequence: 50,
    nowMs: 1000,
    hydrationInFlight: false,
  });
}

describe("ConnectionTooltip", () => {
  it("renders every sub-indicator", () => {
    renderWithProviders(<ConnectionTooltip summary={syntheticSummary()} id="t" />);
    expect(screen.getByRole("status", { name: /Connection phase Live/i })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: /Heartbeat/i })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: /Hydrations 1/i })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: /Replay cursor/i })).toBeInTheDocument();
  });

  it("renders the clients + runtime details", () => {
    renderWithProviders(<ConnectionTooltip summary={syntheticSummary()} id="t" />);
    expect(screen.getByText(/clients/i)).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText(/runtime/i)).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
  });
});
